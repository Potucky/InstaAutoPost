import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Upload, Plus, Archive } from 'lucide-react'
import { format } from 'date-fns'
import { supabase, supabaseUrl, supabaseAnonKey } from '../lib/supabase'
import { useAuth } from '../lib/auth'
import StatusPill from '../components/StatusPill'
import type { ContentItem, ContentStatus } from '../lib/types'

type SlotInfo = {
  scheduled_at: string
  slot_window: string
  slot_status: string
  queue_status: string | null
}

const TABS: { label: string; value: ContentStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Draft', value: 'draft' },
  { label: 'Approved', value: 'approved' },
  { label: 'Archived', value: 'archived' },
]

export default function ContentLibrary() {
  const { user } = useAuth()
  const [items, setItems] = useState<ContentItem[]>([])
  const [slots, setSlots] = useState<Map<string, SlotInfo>>(new Map())
  const [filter, setFilter] = useState<ContentStatus | 'all'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [publishingNow, setPublishingNow] = useState<string | null>(null)
  const [publishConfirmItem, setPublishConfirmItem] = useState<ContentItem | null>(null)
  const [publishConfirmed, setPublishConfirmed] = useState(false)

  async function load() {
    setLoading(true)
    let q = supabase.from('ig_content_library').select('*').order('created_at', { ascending: false })
    if (filter !== 'all') q = q.eq('content_status', filter)
    const { data, error: err } = await q
    if (err) {
      setError(err.message)
      setLoading(false)
      return
    }
    const loaded = data ?? []
    setItems(loaded)

    if (loaded.length > 0) {
      const ids = loaded.map((i) => i.id)
      const { data: slotRows } = await supabase
        .from('ig_schedule_slots')
        .select('content_id, scheduled_at, slot_window, slot_status, ig_publishing_queue(queue_status)')
        .in('content_id', ids)
      const map = new Map<string, SlotInfo>()
      for (const s of slotRows ?? []) {
        if (s.content_id) {
          const qRow = s.ig_publishing_queue as unknown as { queue_status: string } | null
          map.set(s.content_id, {
            scheduled_at: s.scheduled_at,
            slot_window: s.slot_window,
            slot_status: s.slot_status,
            queue_status: qRow?.queue_status ?? null,
          })
        }
      }
      setSlots(map)
    } else {
      setSlots(new Map())
    }

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

  const isCarouselContent = (item: ContentItem) =>
    String(item.media_type ?? '').trim().toLowerCase() === 'carousel'

  async function handlePublishNow(item: ContentItem) {
    if (publishingNow === item.id) return
    if (isCarouselContent(item)) {
      alert('Carousel publishing is not implemented yet.')
      return
    }
    setPublishingNow(item.id)
    try {
      // Duplicate guard: reject if an active (non-terminal) queue row already exists.
      // Terminal statuses (published, cancelled, failed at max attempts) are not blocked
      // so the user can re-queue after a prior run completes.
      const { data: existing } = await supabase
        .from('ig_publishing_queue')
        .select('id, queue_status')
        .eq('content_id', item.id)
        .in('queue_status', ['ready', 'scheduled', 'processing', 'retry_scheduled'])
        .is('published_at', null)
        .is('external_media_id', null)
        .limit(1)

      if (existing && existing.length > 0) {
        alert(
          `Already queued: a "${existing[0].queue_status}" queue item exists for this video.\n` +
          'Cancel it first or wait for it to complete before queuing again.'
        )
        return
      }

      // Create the queue row and get back the inserted ID
      const { data: inserted, error: insertErr } = await supabase
        .from('ig_publishing_queue')
        .insert({
          content_id: item.id,
          queue_status: 'ready',
          scheduled_at: new Date().toISOString(),
          created_by: user?.id ?? null,
        })
        .select('id')
        .single()

      if (insertErr || !inserted) {
        alert(`Error creating queue item: ${insertErr?.message ?? 'Unknown error'}`)
        return
      }

      // Post-insert duplicate guard: catch the narrow race window (e.g. two tabs
      // both passing the pre-insert check before either insert committed).
      // If any OTHER active row for this content exists, cancel ours and abort.
      const { data: raceRows } = await supabase
        .from('ig_publishing_queue')
        .select('id')
        .eq('content_id', item.id)
        .in('queue_status', ['ready', 'scheduled', 'processing', 'retry_scheduled'])
        .is('published_at', null)
        .is('external_media_id', null)
        .neq('id', inserted.id)
        .limit(1)

      if (raceRows && raceRows.length > 0) {
        await supabase
          .from('ig_publishing_queue')
          .update({ queue_status: 'cancelled' })
          .eq('id', inserted.id)
        alert(
          'Another publish was triggered at the same time for this video.\n' +
          'Check the Publishing Queue for the active item.'
        )
        load()
        return
      }

      // Trigger the publish workflow via the Edge Function.
      // The Edge Function holds the GitHub PAT — no secret is sent from the browser.
      // Use direct fetch instead of supabase.functions.invoke so the JSON error body
      // is readable on non-2xx (invoke swallows it into a generic message).
      const { data: { session } } = await supabase.auth.getSession()
      const triggerResp = await fetch(`${supabaseUrl}/functions/v1/trigger-publish`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'apikey': supabaseAnonKey,
          'Authorization': `Bearer ${session?.access_token ?? ''}`,
        },
        body: JSON.stringify({ queue_id: inserted.id }),
      })

      if (!triggerResp.ok) {
        // Trigger failed — do NOT cancel the queue item. 'ready' items are picked up
        // by the scheduled worker (every 5 min) so the publish can still proceed.
        // Only an explicit user action may set queue_status to 'cancelled'.
        // Record the specific failure cause in failure_reason for Logs & Attempts.
        let triggerReason = `Workflow trigger failed: trigger-publish returned ${triggerResp.status}`
        try {
          const respBody = await triggerResp.json() as { error?: string }
          if (respBody?.error && typeof respBody.error === 'string') {
            triggerReason = `Workflow trigger failed: ${respBody.error}`
          }
        } catch {
          // keep status-code-only reason if body is not JSON
        }

        await supabase
          .from('ig_publishing_queue')
          .update({ failure_reason: triggerReason })
          .eq('id', inserted.id)
          .is('published_at', null)
          .is('external_media_id', null)

        alert(
          'Publish workflow could not be triggered. The item was not cancelled.\n\n' +
          'Check Logs & Attempts, then retry.'
        )
      } else {
        alert('Publish workflow triggered! Check the Publishing Queue for live status.')
      }

      load()
    } finally {
      setPublishingNow(null)
    }
  }

  async function handleAddToQueue(item: ContentItem) {
    if (isCarouselContent(item)) {
      alert('Carousel publishing is not implemented yet.')
      return
    }
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

  function formatET(iso: string) {
    return new Date(iso).toLocaleString('en-US', {
      timeZone: 'America/New_York',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }) + ' ET'
  }

  return (
    <div className="min-w-0">
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
            <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="table-th py-2">Title</th>
                  <th className="table-th py-2">Status</th>
                  <th className="table-th py-2">Type</th>
                  <th className="table-th py-2">Size</th>
                  <th className="table-th py-2">Created</th>
                  <th className="table-th py-2 whitespace-nowrap">Scheduled ET</th>
                  <th className="table-th py-2 whitespace-nowrap">Slot Status</th>
                  <th className="table-th py-2">Window</th>
                  <th className="table-th py-2 whitespace-nowrap">Queue Status</th>
                  <th className="table-th py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const slot = slots.get(item.id)
                  return (
                  <tr key={item.id} className="table-tr">
                    <td className="table-td py-2">
                      <div>
                        <p className="font-medium text-slate-900">{item.title}</p>
                        {item.caption && (
                          <p className="text-xs text-slate-400 truncate max-w-[240px]">{item.caption}</p>
                        )}
                      </div>
                    </td>
                    <td className="table-td py-2"><StatusPill status={item.content_status} /></td>
                    <td className="table-td py-2 text-slate-500 uppercase text-xs">{item.media_type}</td>
                    <td className="table-td py-2 text-slate-500">{formatSize(item.file_size)}</td>
                    <td className="table-td py-2 text-slate-500">
                      {format(new Date(item.created_at), 'MMM d, yyyy')}
                    </td>
                    <td className="table-td py-2 whitespace-nowrap text-xs text-slate-600">
                      {slot
                        ? formatET(slot.scheduled_at)
                        : <span className="text-slate-400">Not scheduled</span>}
                    </td>
                    <td className="table-td py-2">
                      {slot
                        ? <StatusPill status={slot.slot_status} />
                        : <span className="text-slate-400 text-xs">No slot</span>}
                    </td>
                    <td className="table-td py-2 text-slate-500 text-xs capitalize">
                      {slot ? slot.slot_window : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="table-td py-2">
                      {slot?.queue_status
                        ? <StatusPill status={slot.queue_status} />
                        : <span className="text-slate-400 text-xs">Not queued</span>}
                    </td>
                    <td className="table-td py-2 w-px">
                      <div className="flex flex-col items-start gap-0.5">
                        {item.content_status === 'draft' && (
                          <button
                            type="button"
                            onClick={() => handleApprove(item.id)}
                            className="text-xs text-emerald-600 hover:text-emerald-700 font-medium whitespace-nowrap"
                          >
                            Approve
                          </button>
                        )}
                        {item.content_status === 'approved' && (
                          isCarouselContent(item) ? (
                            <span
                              className="text-xs text-slate-400 italic whitespace-nowrap"
                              title="Carousel publishing is not implemented yet."
                            >
                              Carousel publishing planned
                            </span>
                          ) : (
                            <>
                              <button
                                type="button"
                                onClick={() => setPublishConfirmItem(item)}
                                disabled={publishingNow === item.id}
                                className="text-xs text-emerald-600 hover:text-emerald-700 font-medium whitespace-nowrap disabled:opacity-40"
                              >
                                {publishingNow === item.id ? '…' : 'Publish Now'}
                              </button>
                              <button
                                type="button"
                                onClick={() => handleAddToQueue(item)}
                                className="text-xs text-violet-600 hover:text-violet-700 font-medium whitespace-nowrap"
                              >
                                + Queue
                              </button>
                            </>
                          )
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
                  )
                })}
              </tbody>
            </table>
            </div>
          )}
        </div>
      </div>

      {publishConfirmItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-sm mx-4 p-6 space-y-4">
            <h2 className="text-sm font-semibold text-slate-900">Confirm publish</h2>
            <p className="text-sm text-slate-700">{publishConfirmItem.title}</p>
            <p className="text-xs text-amber-600 font-medium">
              This will publish to Instagram immediately.
            </p>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={publishConfirmed}
                onChange={(e) => setPublishConfirmed(e.target.checked)}
                disabled={publishingNow === publishConfirmItem.id}
                className="mt-0.5 h-4 w-4 accent-emerald-600 disabled:opacity-40"
              />
              <span className="text-xs text-slate-700">
                I understand this will publish to Instagram immediately and cannot be undone.
              </span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => { setPublishConfirmItem(null); setPublishConfirmed(false) }}
                disabled={publishingNow === publishConfirmItem.id}
                className="text-xs px-3 py-1.5 rounded-md border border-gray-200 text-slate-600 hover:bg-gray-50 disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const item = publishConfirmItem
                  setPublishConfirmItem(null)
                  setPublishConfirmed(false)
                  handlePublishNow(item)
                }}
                disabled={publishingNow === publishConfirmItem.id || !publishConfirmed}
                className="text-xs px-3 py-1.5 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {publishingNow === publishConfirmItem.id ? '…' : 'Confirm Publish'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
