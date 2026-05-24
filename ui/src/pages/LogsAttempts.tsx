import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import { RefreshCw, ChevronDown, ChevronRight } from 'lucide-react'
import { supabase } from '../lib/supabase'
import StatusPill from '../components/StatusPill'
import type { PublishAttempt, AttemptStatus } from '../lib/types'

const TABS: { label: string; value: AttemptStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Success', value: 'success' },
  { label: 'Failed', value: 'failed' },
  { label: 'Dry Run', value: 'dry_run' },
]

export default function LogsAttempts() {
  const [attempts, setAttempts] = useState<PublishAttempt[]>([])
  const [filter, setFilter] = useState<AttemptStatus | 'all'>('all')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setLoadError(null)
    let q = supabase
      .from('ig_publish_attempts')
      .select(`
        *,
        ig_publishing_queue(
          id, content_id, queue_status,
          ig_content_library(id, title)
        )
      `)
      .order('created_at', { ascending: false })
      .limit(100)
    if (filter !== 'all') q = q.eq('status', filter)
    const { data, error } = await q
    if (error) {
      console.error('Failed to load publish attempts:', error.message)
      setLoadError(error.message)
    }
    setAttempts((data ?? []) as PublishAttempt[])
    setLoading(false)
  }

  useEffect(() => { load() }, [filter]) // eslint-disable-line react-hooks/exhaustive-deps

  function toggle(id: string) {
    setExpanded(expanded === id ? null : id)
  }

  function formatDuration(ms: number | null) {
    if (!ms) return '—'
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
  }

  return (
    <div>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">Logs & Attempts</h1>
          <p className="page-subtitle">Full publish audit log — last 100 records</p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="page-body space-y-4">
        {/* Tabs */}
        <div className="flex gap-1 bg-white border border-gray-200 rounded-lg p-1 w-fit">
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

        {loadError && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <p className="font-medium">Unable to load publish attempts.</p>
            <p className="mt-1 font-mono text-xs">{loadError}</p>
          </div>
        )}

        <div className="card overflow-hidden">
          {loading ? (
            <div className="empty-state">Loading...</div>
          ) : attempts.length === 0 ? (
            <div className="empty-state">
              <p className="text-sm">No attempts logged yet.</p>
              <p className="text-xs mt-1 text-slate-400">Run the publisher worker to see logs here.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-th w-8" />
                  <th className="table-th">Video</th>
                  <th className="table-th">Status</th>
                  <th className="table-th">Attempt #</th>
                  <th className="table-th">Dry Run</th>
                  <th className="table-th">Duration</th>
                  <th className="table-th">Attempted At</th>
                  <th className="table-th">Media ID</th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((a) => (
                  <>
                    <tr
                      key={a.id}
                      className={['table-tr cursor-pointer', expanded === a.id ? 'bg-gray-50' : ''].join(' ')}
                      onClick={() => toggle(a.id)}
                    >
                      <td className="table-td text-slate-400">
                        {expanded === a.id
                          ? <ChevronDown size={14} />
                          : <ChevronRight size={14} />}
                      </td>
                      <td className="table-td">
                        <p className="font-medium text-slate-900 max-w-[160px] truncate">
                          {a.ig_publishing_queue?.ig_content_library?.title ?? a.queue_id.slice(0, 8)}
                        </p>
                        <p className="text-xs text-slate-400 font-mono">{a.queue_id.slice(0, 8)}</p>
                      </td>
                      <td className="table-td"><StatusPill status={a.status} /></td>
                      <td className="table-td text-slate-500">#{a.attempt_number}</td>
                      <td className="table-td">
                        {a.dry_run
                          ? <span className="text-violet-600 text-xs font-medium">Yes</span>
                          : <span className="text-slate-400 text-xs">No</span>}
                      </td>
                      <td className="table-td text-slate-500">{formatDuration(a.duration_ms)}</td>
                      <td className="table-td text-slate-500 text-xs">
                        {format(new Date(a.created_at), 'MMM d, HH:mm:ss')}
                      </td>
                      <td className="table-td font-mono text-xs text-slate-500">
                        {a.media_id ?? '—'}
                      </td>
                    </tr>
                    {expanded === a.id && (
                      <tr key={`${a.id}-detail`} className="bg-gray-50">
                        <td colSpan={8} className="px-6 py-4">
                          <div className="grid grid-cols-2 gap-4 text-xs">
                            <div>
                              <p className="text-slate-500 font-medium mb-1">Container ID</p>
                              <p className="font-mono text-slate-700">{a.container_id ?? '—'}</p>
                            </div>
                            <div>
                              <p className="text-slate-500 font-medium mb-1">Worker Version</p>
                              <p className="font-mono text-slate-700">{a.worker_version ?? '—'}</p>
                            </div>
                            {a.error_message && (
                              <div className="col-span-2">
                                <p className="text-red-500 font-medium mb-1">Error</p>
                                <pre className="bg-red-50 border border-red-100 rounded-lg p-3 text-red-700 whitespace-pre-wrap font-mono">
                                  {a.error_message}
                                </pre>
                              </div>
                            )}
                            {a.response_data && (
                              <div className="col-span-2">
                                <p className="text-slate-500 font-medium mb-1">Response Data</p>
                                <pre className="bg-slate-900 text-emerald-400 rounded-lg p-3 text-xs overflow-auto max-h-40 font-mono">
                                  {JSON.stringify(a.response_data, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
