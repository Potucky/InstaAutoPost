import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LayoutGrid, Clock, CheckCircle, AlertCircle, ArrowRight, CalendarCheck } from 'lucide-react'
import { format, startOfDay } from 'date-fns'
import { supabase } from '../lib/supabase'
import StatusPill from '../components/StatusPill'
import type { QueueItem } from '../lib/types'

interface Stats {
  totalContent: number
  scheduled: number
  publishedToday: number
  failed: number
  preparedUntilJul1: number
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>({ totalContent: 0, scheduled: 0, publishedToday: 0, failed: 0, preparedUntilJul1: 0 })
  const [recent, setRecent] = useState<QueueItem[]>([])
  const [nextItem, setNextItem] = useState<QueueItem | null | undefined>(undefined)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const todayStart = startOfDay(new Date()).toISOString()

      const [totalRes, scheduledRes, publishedRes, failedRes, preparedRes, recentRes, nextRes] = await Promise.all([
        supabase.from('ig_content_library').select('*', { count: 'exact', head: true }),
        supabase.from('ig_publishing_queue').select('*', { count: 'exact', head: true })
          .in('queue_status', ['scheduled', 'ready', 'retry_scheduled']),
        supabase.from('ig_publishing_queue').select('*', { count: 'exact', head: true })
          .eq('queue_status', 'published').gte('published_at', todayStart),
        supabase.from('ig_publishing_queue').select('*', { count: 'exact', head: true })
          .eq('queue_status', 'failed'),
        supabase.from('ig_publishing_queue').select('*', { count: 'exact', head: true })
          .in('queue_status', ['scheduled', 'ready', 'retry_scheduled'])
          .lt('scheduled_at', '2026-07-02T00:00:00.000Z'),
        supabase.from('ig_publishing_queue')
          .select('*, ig_content_library(id, title, video_url, content_status)')
          .order('updated_at', { ascending: false })
          .limit(8),
        supabase.from('ig_publishing_queue')
          .select('*, ig_content_library(id, title, video_url, content_status)')
          .in('queue_status', ['scheduled', 'ready'])
          .is('published_at', null)
          .is('external_media_id', null)
          .order('scheduled_at', { ascending: true })
          .limit(1),
      ])

      setStats({
        totalContent: totalRes.count ?? 0,
        scheduled: scheduledRes.count ?? 0,
        publishedToday: publishedRes.count ?? 0,
        failed: failedRes.count ?? 0,
        preparedUntilJul1: preparedRes.count ?? 0,
      })
      setRecent((recentRes.data ?? []) as QueueItem[])
      setNextItem(((nextRes.data ?? []) as QueueItem[])[0] ?? null)
      setLoading(false)
    }
    load()
  }, [])

  const statCards = [
    { label: 'Total Content', value: stats.totalContent, icon: LayoutGrid, color: 'text-violet-600', bg: 'bg-violet-50' },
    { label: 'Queued / Scheduled', value: stats.scheduled, icon: Clock, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Published Today', value: stats.publishedToday, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Failed', value: stats.failed, icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'Prepared ≤ Jul 1', value: stats.preparedUntilJul1, icon: CalendarCheck, color: 'text-teal-600', bg: 'bg-teal-50' },
  ]

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">InstaAutoPost — Instagram Autoposting Control Center</p>
      </div>

      <div className="page-body space-y-8">
        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {statCards.map(({ label, value, icon: Icon, color, bg }) => (
            <div key={label} className="stat-card flex items-start gap-4">
              <div className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center shrink-0`}>
                <Icon size={20} className={color} />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{loading ? '—' : value}</p>
                <p className="text-xs text-slate-500 mt-0.5">{label}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Next to publish */}
        <div className="card px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900 mb-3">Next to Publish</h2>
          {loading || nextItem === undefined ? (
            <p className="text-sm text-slate-400">Loading...</p>
          ) : nextItem === null ? (
            <p className="text-sm text-slate-500">No items scheduled or ready.</p>
          ) : (
            <div className="flex flex-wrap items-center gap-4">
              <span className="font-medium text-slate-900 truncate max-w-[240px]">
                {nextItem.ig_content_library?.title ?? nextItem.content_id.slice(0, 8)}
              </span>
              <StatusPill status={nextItem.queue_status} />
              <span className="text-xs text-slate-500">
                {nextItem.scheduled_at ? format(new Date(nextItem.scheduled_at), 'MMM d, HH:mm') : 'No time set'}
              </span>
              <span className="text-xs text-slate-400">
                Attempt {nextItem.attempt_count}/{nextItem.max_attempts}
              </span>
            </div>
          )}
        </div>

        {/* Recent Queue */}
        <div className="card">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-slate-900">Recent Queue Activity</h2>
            <Link to="/queue" className="text-xs text-violet-600 hover:text-violet-700 flex items-center gap-1">
              View all <ArrowRight size={12} />
            </Link>
          </div>

          {loading ? (
            <div className="empty-state text-sm">Loading...</div>
          ) : recent.length === 0 ? (
            <div className="empty-state">
              <p className="text-sm">No queue activity yet.</p>
              <Link to="/upload" className="mt-3 btn-primary text-xs">Add your first video</Link>
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-th">Content</th>
                  <th className="table-th">Status</th>
                  <th className="table-th">Scheduled</th>
                  <th className="table-th">Published</th>
                  <th className="table-th">Attempts</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((item) => (
                  <tr key={item.id} className="table-tr">
                    <td className="table-td font-medium text-slate-900 max-w-[200px] truncate">
                      {item.ig_content_library?.title ?? item.content_id.slice(0, 8)}
                    </td>
                    <td className="table-td">
                      <StatusPill status={item.queue_status} />
                    </td>
                    <td className="table-td text-slate-500">
                      {item.scheduled_at ? format(new Date(item.scheduled_at), 'MMM d, HH:mm') : '—'}
                    </td>
                    <td className="table-td text-slate-500">
                      {item.published_at ? format(new Date(item.published_at), 'MMM d, HH:mm') : '—'}
                    </td>
                    <td className="table-td">
                      <span className="text-slate-500">{item.attempt_count}/{item.max_attempts}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Quick Actions */}
        <div className="card px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900 mb-3">Quick Actions</h2>
          <div className="flex flex-wrap gap-3">
            <Link to="/upload" className="btn-primary">Upload Video</Link>
            <Link to="/queue" className="btn-secondary">Manage Queue</Link>
            <Link to="/logs" className="btn-secondary">View Logs</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
