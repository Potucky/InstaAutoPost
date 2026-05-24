import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import { RefreshCw, XCircle } from 'lucide-react'
import { supabase } from '../lib/supabase'
import StatusPill from '../components/StatusPill'
import WorkflowDisabledBanner from '../components/WorkflowDisabledBanner'
import type { QueueItem, QueueStatus } from '../lib/types'

const TABS: { label: string; value: QueueStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Scheduled', value: 'scheduled' },
  { label: 'Ready', value: 'ready' },
  { label: 'Processing', value: 'processing' },
  { label: 'Published', value: 'published' },
  { label: 'Failed', value: 'failed' },
]

export default function PublishingQueue() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [filter, setFilter] = useState<QueueStatus | 'all'>('all')
  const [loading, setLoading] = useState(true)
  const [schedulingId, setSchedulingId] = useState<string | null>(null)
  const [scheduleAt, setScheduleAt] = useState('')

  async function load() {
    setLoading(true)
    let q = supabase
      .from('ig_publishing_queue')
      .select('*, ig_content_library(id, title, content_status, caption)')
      .order('scheduled_at', { ascending: true, nullsFirst: false })
      .order('created_at', { ascending: false })
    if (filter !== 'all') q = q.eq('queue_status', filter)
    const { data } = await q
    setItems((data ?? []) as QueueItem[])
    setLoading(false)
  }

  useEffect(() => { load() }, [filter]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSchedule(id: string) {
    if (!scheduleAt) return
    const { data, error } = await supabase
      .from('ig_publishing_queue')
      .update({ queue_status: 'scheduled', scheduled_at: new Date(scheduleAt).toISOString() })
      .eq('id', id)
      .eq('queue_status', 'draft')
      .is('published_at', null)
      .is('external_media_id', null)
      .select('id')
    if (error) {
      alert(error.message)
    } else if (!data || data.length === 0) {
      alert('Could not schedule — item may already be published, processing, or no longer a draft.')
    }
    setSchedulingId(null)
    setScheduleAt('')
    load()
  }

  async function handleMarkReady(id: string) {
    const { data, error } = await supabase
      .from('ig_publishing_queue')
      .update({ queue_status: 'ready' })
      .eq('id', id)
      .eq('queue_status', 'scheduled')
      .is('published_at', null)
      .is('external_media_id', null)
      .select('id')
    if (error) {
      alert(error.message)
    } else if (!data || data.length === 0) {
      alert('Could not mark ready — item may already be published, processing, or no longer scheduled.')
    }
    load()
  }

  async function handleCancel(item: QueueItem) {
    if (!confirm('Cancel this queue item?')) return
    // Local guard: fast-fail before hitting the DB
    if (item.external_media_id || item.published_at) return
    if (!actionable(item.queue_status)) return
    const { data } = await supabase
      .from('ig_publishing_queue')
      .update({ queue_status: 'cancelled' })
      .eq('id', item.id)
      .is('external_media_id', null)
      .is('published_at', null)
      .in('queue_status', ['draft', 'scheduled', 'ready', 'retry_scheduled', 'failed'])
      .select()
    if (!data || data.length === 0) {
      console.warn(`handleCancel: no row updated for id=${item.id} — row state may have changed`)
    }
    load()
  }

  async function handleRetry(item: QueueItem) {
    // Local guard: fast-fail before hitting the DB
    if (item.external_media_id || item.published_at) return
    if (item.queue_status !== 'failed') return
    if (item.attempt_count >= item.max_attempts) return
    const { data } = await supabase
      .from('ig_publishing_queue')
      .update({ queue_status: 'retry_scheduled', next_retry_at: new Date().toISOString(), failure_reason: null })
      .eq('id', item.id)
      .is('external_media_id', null)
      .is('published_at', null)
      .eq('queue_status', 'failed')
      .lt('attempt_count', item.max_attempts)
      .select()
    if (!data || data.length === 0) {
      console.warn(`handleRetry: no row updated for id=${item.id} — row state may have changed`)
    }
    load()
  }

  const actionable = (s: QueueStatus) => ['draft', 'scheduled', 'ready', 'retry_scheduled', 'failed'].includes(s)

  return (
    <div className="min-w-0">
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Publishing Queue</h1>
          <p className="page-subtitle">{items.length} item{items.length !== 1 ? 's' : ''}</p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="page-body space-y-4">
        <WorkflowDisabledBanner />

        {/* Tabs */}
        <div className="flex flex-wrap gap-1 bg-white border border-gray-200 rounded-lg p-1 w-fit">
          {TABS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setFilter(value)}
              className={[
                'px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                filter === value ? 'bg-violet-600 text-white' : 'text-slate-600 hover:bg-gray-100',
              ].join(' ')}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="card overflow-hidden">
          {loading ? (
            <div className="empty-state">Loading...</div>
          ) : items.length === 0 ? (
            <div className="empty-state">
              <p className="text-sm">No items in this view.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-th">Content</th>
                  <th className="table-th">Status</th>
                  <th className="table-th">Scheduled At</th>
                  <th className="table-th">Published At</th>
                  <th className="table-th">Attempts</th>
                  <th className="table-th">Error</th>
                  <th className="table-th">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <>
                    <tr key={item.id} className="table-tr">
                      <td className="table-td">
                        <p className="font-medium text-slate-900 max-w-[180px] truncate">
                          {item.ig_content_library?.title ?? item.content_id.slice(0, 8)}
                        </p>
                        {item.ig_content_library?.caption && (
                          <p className="text-xs text-slate-400 max-w-[180px] line-clamp-2 leading-tight mt-0.5">
                            {item.ig_content_library.caption}
                          </p>
                        )}
                        <p className="text-xs text-slate-400 font-mono">{item.id.slice(0, 8)}</p>
                      </td>
                      <td className="table-td"><StatusPill status={item.queue_status} /></td>
                      <td className="table-td text-slate-500 text-xs">
                        {item.scheduled_at ? format(new Date(item.scheduled_at), 'MMM d, HH:mm') : '—'}
                      </td>
                      <td className="table-td text-slate-500 text-xs">
                        {item.published_at ? format(new Date(item.published_at), 'MMM d, HH:mm') : '—'}
                      </td>
                      <td className="table-td">
                        <span className={item.attempt_count >= item.max_attempts ? 'text-red-500 font-medium' : 'text-slate-500'}>
                          {item.attempt_count}/{item.max_attempts}
                        </span>
                      </td>
                      <td className="table-td max-w-[180px]">
                        {item.failure_reason ? (
                          <span className="text-xs text-red-500 truncate block" title={item.failure_reason}>
                            {item.failure_reason.slice(0, 60)}{item.failure_reason.length > 60 ? '…' : ''}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="table-td">
                        {(() => {
                          const hasProof = !!(item.external_media_id || item.published_at)
                          if (hasProof && item.queue_status === 'failed') {
                            return (
                              <span className="text-xs text-amber-700 font-medium truncate block max-w-[200px]" title={`external_media_id: ${item.external_media_id ?? 'n/a'}`}>
                                Published proof exists — manual reconciliation only
                              </span>
                            )
                          }
                          return (
                            <div className="flex items-center gap-2">
                              {item.queue_status === 'draft' && (
                                <button
                                  onClick={() => setSchedulingId(schedulingId === item.id ? null : item.id)}
                                  className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                                >
                                  Schedule
                                </button>
                              )}
                              {item.queue_status === 'scheduled' && (
                                <button
                                  onClick={() => handleMarkReady(item.id)}
                                  className="text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                                >
                                  Mark Ready
                                </button>
                              )}
                              {item.queue_status === 'failed' && !hasProof && item.attempt_count < item.max_attempts && (
                                <button
                                  onClick={() => handleRetry(item)}
                                  className="text-xs text-orange-600 hover:text-orange-700 font-medium"
                                >
                                  Retry
                                </button>
                              )}
                              {actionable(item.queue_status) && !hasProof && (
                                <button
                                  onClick={() => handleCancel(item)}
                                  className="text-slate-400 hover:text-red-500"
                                  title="Cancel"
                                >
                                  <XCircle size={14} />
                                </button>
                              )}
                            </div>
                          )
                        })()}
                      </td>
                    </tr>
                    {schedulingId === item.id && (
                      <tr key={`${item.id}-schedule`} className="bg-blue-50">
                        <td colSpan={7} className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <label className="text-xs text-slate-600 font-medium whitespace-nowrap">Schedule at:</label>
                            <input
                              type="datetime-local"
                              className="input max-w-xs text-xs"
                              value={scheduleAt}
                              onChange={(e) => setScheduleAt(e.target.value)}
                            />
                            <button
                              onClick={() => handleSchedule(item.id)}
                              className="btn-primary text-xs py-1.5"
                            >
                              Confirm
                            </button>
                            <button
                              onClick={() => setSchedulingId(null)}
                              className="btn-secondary text-xs py-1.5"
                            >
                              Cancel
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
