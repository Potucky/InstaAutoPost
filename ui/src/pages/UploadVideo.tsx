import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Video, CheckCircle, Upload, Loader2, X } from 'lucide-react'
import { supabase } from '../lib/supabase'
import { useAuth } from '../lib/auth'

const STORAGE_BUCKET = 'instaautopost-media'
const MAX_VIDEO_UPLOAD_BYTES = 45 * 1024 * 1024

interface FormData {
  title: string
  caption: string
  video_url: string
  thumbnail_url: string
  hashtag_input: string
  duration_seconds: string
  media_type: string
}

const DEFAULTS: FormData = {
  title: '',
  caption: '',
  video_url: '',
  thumbnail_url: '',
  hashtag_input: '',
  duration_seconds: '',
  media_type: 'video',
}

function sanitizeFilename(name: string): string {
  return name.replace(/[^a-zA-Z0-9._-]/g, '_').replace(/_{2,}/g, '_')
}

function fallbackUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export default function UploadVideo() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [form, setForm] = useState<FormData>(DEFAULTS)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [uploadedPath, setUploadedPath] = useState<string | null>(null)
  const [uploadedPublicUrl, setUploadedPublicUrl] = useState<string | null>(null)

  function set(field: keyof FormData, value: string) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function parseHashtags(raw: string): string[] {
    return raw
      .split(/[\s,]+/)
      .map((h) => (h.startsWith('#') ? h : `#${h}`))
      .filter((h) => h.length > 1)
  }

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    if (!user?.id) {
      setUploadError('You must be signed in to upload files.')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    const isMP4 =
      file.type === 'video/mp4' ||
      (file.type === '' && file.name.toLowerCase().endsWith('.mp4'))

    if (file.size === 0) {
      setUploadError('Selected file is empty.')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }
    if (!isMP4) {
      setUploadError('Only MP4 files are accepted.')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }
    if (file.size > MAX_VIDEO_UPLOAD_BYTES) {
      setUploadError(
        `File exceeds the 45 MB upload limit (${(file.size / 1024 / 1024).toFixed(1)} MB).`
      )
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setSelectedFile(file)
    setUploadError(null)
    setUploadedPath(null)
    setUploadedPublicUrl(null)
    set('video_url', '')
    setUploading(true)

    const safeName = sanitizeFilename(file.name)
    let uuid: string
    try {
      uuid = crypto.randomUUID()
    } catch {
      uuid = fallbackUUID()
    }
    const storagePath = `${user.id}/${uuid}_${safeName}`

    const { error: uploadErr } = await supabase.storage
      .from(STORAGE_BUCKET)
      .upload(storagePath, file, { upsert: false })

    if (uploadErr) {
      setUploadError(`Upload failed: ${uploadErr.message}`)
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      setUploading(false)
      return
    }

    const { data: urlData } = supabase.storage
      .from(STORAGE_BUCKET)
      .getPublicUrl(storagePath)

    setUploadedPath(storagePath)
    setUploadedPublicUrl(urlData.publicUrl)
    set('video_url', urlData.publicUrl)
    setUploading(false)
  }

  async function bestEffortRemoveUpload(path: string, publicUrl: string) {
    try {
      const { data: rows, error: lookupErr } = await supabase
        .from('ig_content_library')
        .select('id')
        .eq('video_url', publicUrl)
        .limit(1)
      if (lookupErr) return
      if (rows?.length === 0) {
        await supabase.storage.from(STORAGE_BUCKET).remove([path])
      }
    } catch {
      // Best-effort; ignore cleanup errors
    }
  }

  async function clearUpload() {
    const pathToRemove = uploadedPath
    const urlToCheck = uploadedPublicUrl
    const currentUrl = form.video_url

    setSelectedFile(null)
    setUploadedPath(null)
    setUploadedPublicUrl(null)
    setUploadError(null)
    set('video_url', '')
    if (fileInputRef.current) fileInputRef.current.value = ''

    if (pathToRemove && urlToCheck && currentUrl === urlToCheck) {
      await bestEffortRemoveUpload(pathToRemove, urlToCheck)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.title.trim() || !form.video_url.trim()) {
      setError('Title and Video URL are required.')
      return
    }
    setSubmitting(true)
    setError(null)

    const { error: err } = await supabase.from('ig_content_library').insert({
      title: form.title.trim(),
      caption: form.caption.trim() || null,
      video_url: form.video_url.trim(),
      thumbnail_url: form.thumbnail_url.trim() || null,
      hashtags: form.hashtag_input.trim() ? parseHashtags(form.hashtag_input) : null,
      duration_seconds: form.duration_seconds ? parseInt(form.duration_seconds, 10) : null,
      file_size: selectedFile ? selectedFile.size : null,
      media_type: form.media_type,
      content_status: 'draft',
      created_by: user?.id ?? null,
    })

    if (err) {
      let errorMsg = err.message
      if (uploadedPath && uploadedPublicUrl && form.video_url.trim() === uploadedPublicUrl) {
        try {
          const { data: rows, error: lookupErr } = await supabase
            .from('ig_content_library')
            .select('id')
            .eq('video_url', uploadedPublicUrl)
            .limit(1)
          if (lookupErr || rows == null) {
            errorMsg += ' Cleanup lookup failed; manual storage cleanup may be needed.'
          } else if (rows.length === 0) {
            const { error: removeErr } = await supabase.storage
              .from(STORAGE_BUCKET)
              .remove([uploadedPath])
            if (removeErr) {
              errorMsg += ' Storage cleanup may be needed for the uploaded file.'
            }
          }
        } catch {
          errorMsg += ' Storage cleanup may be needed for the uploaded file.'
        }
      }
      setError(errorMsg)
      setSubmitting(false)
      return
    }

    setSuccess(true)
    setSubmitting(false)
    setTimeout(() => navigate('/content'), 1500)
  }

  if (success) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">Upload Video</h1>
        </div>
        <div className="page-body">
          <div className="card max-w-md mx-auto p-8 flex flex-col items-center text-center">
            <CheckCircle size={40} className="text-emerald-500 mb-3" />
            <p className="font-semibold text-slate-900">Video added to Content Library</p>
            <p className="text-sm text-slate-500 mt-1">Redirecting to Content Library...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Upload Video</h1>
        <p className="page-subtitle">Add a new video asset to the Content Library</p>
      </div>

      <div className="page-body">
        <div className="card max-w-xl p-6">
          <div className="flex items-center gap-3 mb-6 pb-4 border-b border-gray-100">
            <div className="w-9 h-9 rounded-xl bg-violet-50 flex items-center justify-center">
              <Video size={18} className="text-violet-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">New Video Asset</p>
              <p className="text-xs text-slate-500">Saved as Draft — approve to schedule</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label" htmlFor="title">Title <span className="text-red-500">*</span></label>
              <input
                id="title"
                className="input"
                placeholder="My Instagram Reel"
                value={form.title}
                onChange={(e) => set('title', e.target.value)}
                required
              />
            </div>

            {/* File Upload */}
            <div>
              <label className="label" htmlFor="video_file">Choose Video File</label>
              <input
                ref={fileInputRef}
                id="video_file"
                type="file"
                accept="video/mp4,.mp4"
                className="hidden"
                onChange={handleFileSelect}
                disabled={uploading}
              />

              {!selectedFile ? (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="w-full flex items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 px-4 py-5 text-sm text-slate-500 hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Upload size={16} />
                  Click to choose a video file
                </button>
              ) : (
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  {uploading ? (
                    <div className="flex items-center gap-2 text-sm text-violet-700">
                      <Loader2 size={15} className="animate-spin shrink-0" />
                      <span className="truncate">Uploading {selectedFile.name}…</span>
                    </div>
                  ) : uploadedPath ? (
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-sm text-emerald-700 min-w-0">
                        <CheckCircle size={15} className="shrink-0" />
                        <span className="truncate">{selectedFile.name}</span>
                      </div>
                      <button
                        type="button"
                        onClick={clearUpload}
                        className="shrink-0 text-slate-400 hover:text-slate-600"
                        title="Remove uploaded file"
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-slate-600">
                      <span className="truncate">{selectedFile.name}</span>
                    </div>
                  )}
                </div>
              )}

              {uploadError && (
                <p className="text-xs text-red-600 mt-1">{uploadError}</p>
              )}
              <p className="text-xs text-slate-400 mt-1">
                MP4 only, max 45 MB. Uploads to Supabase Storage; URL is filled automatically.
              </p>
            </div>

            <div>
              <label className="label" htmlFor="video_url">
                Video URL <span className="text-red-500">*</span>
                {uploadedPath && (
                  <span className="ml-2 text-xs font-normal text-emerald-600">(auto-filled from upload)</span>
                )}
              </label>
              <input
                id="video_url"
                className="input"
                type="url"
                placeholder="https://…"
                value={form.video_url}
                onChange={(e) => set('video_url', e.target.value)}
                required
              />
              <p className="text-xs text-slate-400 mt-1">
                {uploadedPath
                  ? 'Auto-filled from your upload. You can still edit this manually.'
                  : 'Or paste a publicly accessible URL directly. Instagram must be able to fetch it.'}
              </p>
            </div>

            <div>
              <label className="label" htmlFor="caption">Caption</label>
              <textarea
                id="caption"
                className="input h-24 resize-none"
                placeholder="Write your caption here..."
                value={form.caption}
                onChange={(e) => set('caption', e.target.value)}
              />
            </div>

            <div>
              <label className="label" htmlFor="hashtag_input">Hashtags</label>
              <input
                id="hashtag_input"
                className="input"
                placeholder="#reel #instagram #content"
                value={form.hashtag_input}
                onChange={(e) => set('hashtag_input', e.target.value)}
              />
              <p className="text-xs text-slate-400 mt-1">Space or comma separated. # is added automatically.</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label" htmlFor="thumbnail_url">Thumbnail URL</label>
                <input
                  id="thumbnail_url"
                  className="input"
                  type="url"
                  placeholder="https://..."
                  value={form.thumbnail_url}
                  onChange={(e) => set('thumbnail_url', e.target.value)}
                />
              </div>
              <div>
                <label className="label" htmlFor="duration_seconds">Duration (seconds)</label>
                <input
                  id="duration_seconds"
                  className="input"
                  type="number"
                  min="1"
                  placeholder="60"
                  value={form.duration_seconds}
                  onChange={(e) => set('duration_seconds', e.target.value)}
                />
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button type="submit" className="btn-primary" disabled={submitting || uploading}>
                {submitting ? 'Saving...' : 'Save to Library'}
              </button>
              <button
                type="button"
                onClick={() => {
                  const path = uploadedPath
                  const url = uploadedPublicUrl
                  const cur = form.video_url
                  if (path && url && cur === url) {
                    void bestEffortRemoveUpload(path, url)
                  }
                  navigate('/content')
                }}
                disabled={uploading}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
