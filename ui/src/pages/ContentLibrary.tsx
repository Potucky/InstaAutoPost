import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Upload, Plus, Archive } from 'lucide-react'
import { format } from 'date-fns'
import { supabase } from '../lib/supabase'
import { useAuth } from '../lib/auth'
import StatusPill from '../components/StatusPill'
import type { ContentItem, ContentStatus } from '../lib/types'

const TABS: { label: string; value: ContentStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Draft', value: 'draft' },
  { label: 'Approved', value: 'approved' },
  { label: 'Archived', value: 'archived' },
]

export default function ContentLibrary() {
  const { user } = useAuth()
  const [items, setItems] = useState<ContentItem[]>([])
  const [filter, setFilter] = useState<ContentStatus | 'all'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    let q = supabase.from('ig_content_library').select('*').order('created_at', { ascending: false })
    if (filter !== 'all') q = q.eq('content_status', filter)
    const { data, error: err } = await q
    if (err) setError(err.message)
    else setItems(data ?? [])
    setLoading(false)
  }

  useEffect(() => { load() }, [filter]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleApprove(id: string) {
    await supabase.from('ig_content_library').update({ content_status: 'approved' }).eq('id', id)
    load()
  }

  async function handleArchive(id: string) {
    await supabase.from('ig_content_library').update({ content_status: 'archived' }).eq('id', id)
    load()
  }

  async function handleAddToQueue(item: ContentItem) {
    const { error: err } = await supabase.from('ig_publishing_queue').insert({
      content_id: item.id,
      queue_status: 'draft',
      created_by: user?.id ?? null,
    })
    if (err) alert(`Error: ${err.message}`)
    else alert('Added to queue as draft. Open Publishing Queue to schedule it.')
  }

  function formatSize(bytes: number | null) {
    if (!bytes) return '—'
    return bytes > 1_000_000 ? `${(bytes / 1_000_000).toFixed(1)} MB` : `${(bytes / 1_000).toFixed(0)} KB`
  }

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Content Library</h1>
          <p className="page-subtitle">All video assets — {items.length} item{items.length !== 1 ? 's' : ''}</p>
        </div>
        <Link to="/upload" className="btn-primary">
          <Plus size={15} /> Add Video
        </Link>
      </div>

      <div className="page-body space-y-4">
        {/* Tabs */}
        <div className="flex gap-1 bg-white border border-gray-200 rounded-lg p-1 w-fit">
          {TABS.map(({ label, value }) => (
            <button
              type="button"
              key={value}
              onClick={() => setFilter(value)}
              className={[
                'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                filter === value
                  ? 'bg-violet-600 text-white'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-gray-100',
              ].join(' ')}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="card overflow-hidden">
          {loading ? (
            <div className="empty-state">Loading...</div>
          ) : error ? (
            <div className="empty-state text-red-500">{error}</div>
          ) : items.length === 0 ? (
            <div className="empty-state">
              <Upload size={32} className="mb-3 text-slate-300" />
              <p className="text-sm">No content yet.</p>
              <Link to="/upload" className="mt-3 btn-primary text-xs">Upload your first video</Link>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-th">Title</th>
                  <th className="table-th">Status</th>
                  <th className="table-th">Type</th>
                  <th className="table-th">Size</th>
                  <th className="table-th">Created</th>
                  <th className="table-th">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="table-tr">
                    <td className="table-td">
                      <div>
                        <p className="font-medium text-slate-900">{item.title}</p>
                        {item.caption && (
                          <p className="text-xs text-slate-400 truncate max-w-[240px]">{item.caption}</p>
                        )}
                      </div>
                    </td>
                    <td className="table-td"><StatusPill status={item.content_status} /></td>
                    <td className="table-td text-slate-500 uppercase text-xs">{item.media_type}</td>
                    <td className="table-td text-slate-500">{formatSize(item.file_size)}</td>
                    <td className="table-td text-slate-500">
                      {format(new Date(item.created_at), 'MMM d, yyyy')}
                    </td>
                    <td className="table-td">
                      <div className="flex items-center gap-2">
                        {item.content_status === 'draft' && (
                          <button
                            type="button"
                            onClick={() => handleApprove(item.id)}
                            className="text-xs text-emerald-600 hover:text-emerald-700 font-medium"
                          >
                            Approve
                          </button>
                        )}
                        {item.content_status === 'approved' && (
                          <button
                            type="button"
                            onClick={() => handleAddToQueue(item)}
                            className="text-xs text-violet-600 hover:text-violet-700 font-medium"
                          >
                            + Queue
                          </button>
                        )}
                        {item.content_status !== 'archived' && (
                          <button
                            type="button"
                            onClick={() => handleArchive(item.id)}
                            className="text-xs text-slate-400 hover:text-slate-600"
                            title="Archive"
                          >
                            <Archive size={13} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
