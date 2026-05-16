import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Video, CheckCircle } from 'lucide-react'
import { supabase } from '../lib/supabase'

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

export default function UploadVideo() {
  const navigate = useNavigate()
  const [form, setForm] = useState<FormData>(DEFAULTS)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function set(field: keyof FormData, value: string) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function parseHashtags(raw: string): string[] {
    return raw
      .split(/[\s,]+/)
      .map((h) => (h.startsWith('#') ? h : `#${h}`))
      .filter((h) => h.length > 1)
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
      media_type: form.media_type,
      content_status: 'draft',
    })

    if (err) {
      setError(err.message)
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

            <div>
              <label className="label" htmlFor="video_url">Video URL <span className="text-red-500">*</span></label>
              <input
                id="video_url"
                className="input"
                type="url"
                placeholder="https://..."
                value={form.video_url}
                onChange={(e) => set('video_url', e.target.value)}
                required
              />
              <p className="text-xs text-slate-400 mt-1">Publicly accessible URL. Instagram must be able to fetch it.</p>
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
              <button type="submit" className="btn-primary" disabled={submitting}>
                {submitting ? 'Saving...' : 'Save to Library'}
              </button>
              <button
                type="button"
                onClick={() => navigate('/content')}
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
