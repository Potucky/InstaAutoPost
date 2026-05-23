import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  getDay,
  isSameDay,
  isToday,
  addMonths,
  subMonths,
} from 'date-fns'
import { supabase } from '../lib/supabase'
import type { ScheduleSlot, SlotStatus } from '../lib/types'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const BADGE_STYLES: Record<SlotStatus, string> = {
  empty:     'bg-slate-100 text-slate-500',
  assigned:  'bg-blue-100 text-blue-700',
  queued:    'bg-violet-100 text-violet-700',
  published: 'bg-emerald-100 text-emerald-700',
  failed:    'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-500',
}

function dayKey(day: Date): string {
  return format(day, 'yyyy-MM-dd')
}

function formatNY(iso: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(new Date(iso))
  const p: Record<string, string> = {}
  for (const part of parts) p[part.type] = part.value
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second} ET`
}

function SlotBadge({ status }: { status: SlotStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${BADGE_STYLES[status] ?? 'bg-gray-100 text-gray-500'}`}>
      {status}
    </span>
  )
}

type StatusCounts = {
  total: number
  empty: number
  assigned: number
  queued: number
  published: number
  failed: number
}

const COUNTER_ITEMS: { label: string; key: keyof StatusCounts; color: string }[] = [
  { label: 'Total', key: 'total', color: 'text-slate-700' },
  { label: 'Empty', key: 'empty', color: 'text-slate-500' },
  { label: 'Assigned', key: 'assigned', color: 'text-blue-600' },
  { label: 'Queued', key: 'queued', color: 'text-violet-600' },
  { label: 'Published', key: 'published', color: 'text-emerald-600' },
  { label: 'Failed', key: 'failed', color: 'text-red-600' },
]

export default function CalendarPage() {
  const [current, setCurrent] = useState(new Date())
  const [monthSlots, setMonthSlots] = useState<ScheduleSlot[]>([])
  const [upcomingSlots, setUpcomingSlots] = useState<ScheduleSlot[]>([])
  const [counts, setCounts] = useState<StatusCounts>({ total: 0, empty: 0, assigned: 0, queued: 0, published: 0, failed: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Date | null>(null)

  // Summary counts + next 50 upcoming slots — runs once on mount
  useEffect(() => {
    async function loadInitial() {
      setLoading(true)
      setError(null)

      const { data: statusRows, error: countErr } = await supabase
        .from('ig_schedule_slots')
        .select('slot_status')

      if (countErr) {
        setError(countErr.message)
        setLoading(false)
        return
      }

      const c: StatusCounts = { total: 0, empty: 0, assigned: 0, queued: 0, published: 0, failed: 0 }
      for (const row of statusRows ?? []) {
        c.total++
        const s = row.slot_status as SlotStatus
        if (s === 'empty') c.empty++
        else if (s === 'assigned') c.assigned++
        else if (s === 'queued') c.queued++
        else if (s === 'published') c.published++
        else if (s === 'failed') c.failed++
      }
      setCounts(c)

      const { data: upcoming, error: upcomingErr } = await supabase
        .from('ig_schedule_slots')
        .select('*, ig_content_library(id, title, media_type)')
        .gte('scheduled_at', new Date().toISOString())
        .order('scheduled_at', { ascending: true })
        .limit(50)

      if (upcomingErr) {
        setError(upcomingErr.message)
        setLoading(false)
        return
      }

      setUpcomingSlots((upcoming ?? []) as ScheduleSlot[])
      setLoading(false)
    }
    loadInitial()
  }, [])

  // Current month slots for the calendar grid — re-fetches on month navigation
  useEffect(() => {
    async function loadMonth() {
      const monthStartKey = format(startOfMonth(current), 'yyyy-MM-dd')
      const monthEndKey = format(endOfMonth(current), 'yyyy-MM-dd')
      const { data, error: monthErr } = await supabase
        .from('ig_schedule_slots')
        .select('*, ig_content_library(id, title, media_type)')
        .gte('slot_date', monthStartKey)
        .lte('slot_date', monthEndKey)
        .order('slot_date', { ascending: true })
        .order('scheduled_at', { ascending: true })
      if (!monthErr) setMonthSlots((data ?? []) as ScheduleSlot[])
    }
    loadMonth()
  }, [current])

  const monthStart = startOfMonth(current)
  const days = eachDayOfInterval({ start: monthStart, end: endOfMonth(current) })
  const startPad = getDay(monthStart)
  const paddingDays = Array.from({ length: startPad })

  function slotsForDay(day: Date) {
    return monthSlots.filter((s) => s.slot_date === dayKey(day))
  }

  const selectedSlots = selected ? slotsForDay(selected) : []

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Schedule</h1>
        <p className="page-subtitle">Schedule slots — {format(current, 'MMMM yyyy')}</p>
      </div>

      <div className="page-body space-y-4">
        {/* Summary counters */}
        <div className="grid grid-cols-6 gap-3">
          {COUNTER_ITEMS.map(({ label, key, color }) => (
            <div key={key} className="card p-3 text-center">
              <p className={`text-2xl font-bold ${color}`}>{counts[key]}</p>
              <p className="text-xs text-slate-500 mt-0.5">{label}</p>
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900">{format(current, 'MMMM yyyy')}</h2>
            <div className="flex gap-1">
              <button
                type="button"
                aria-label="Previous month"
                onClick={() => setCurrent(subMonths(current, 1))}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-slate-600 transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                type="button"
                onClick={() => setCurrent(new Date())}
                className="px-2.5 py-1 rounded-lg hover:bg-gray-100 text-xs text-slate-600 font-medium transition-colors"
              >
                Today
              </button>
              <button
                type="button"
                aria-label="Next month"
                onClick={() => setCurrent(addMonths(current, 1))}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-slate-600 transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-7 gap-1 mb-1">
            {WEEKDAYS.map((d) => (
              <div key={d} className="text-center text-xs font-medium text-slate-400 py-1">{d}</div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-1">
            {paddingDays.map((_, i) => (
              <div key={`pad-${i}`} className="h-20 rounded-lg" />
            ))}
            {days.map((day) => {
              const daySlots = slotsForDay(day)
              const isSelected = selected && isSameDay(day, selected)
              return (
                <button
                  key={day.toISOString()}
                  type="button"
                  onClick={() => setSelected(isSameDay(day, selected ?? new Date(0)) ? null : day)}
                  className={[
                    'h-20 rounded-lg p-1.5 text-left transition-colors border',
                    isToday(day) ? 'border-violet-300 bg-violet-50' : 'border-transparent hover:border-gray-200 hover:bg-gray-50',
                    isSelected ? 'border-violet-500 bg-violet-50 ring-1 ring-violet-300' : '',
                  ].join(' ')}
                >
                  <span className={[
                    'text-xs font-medium block mb-1',
                    isToday(day) ? 'text-violet-600' : 'text-slate-600',
                  ].join(' ')}>
                    {format(day, 'd')}
                  </span>
                  <div className="space-y-0.5">
                    {daySlots.slice(0, 2).map((slot) => (
                      <div
                        key={slot.id}
                        className={`text-[10px] rounded px-1 py-0.5 truncate font-medium ${BADGE_STYLES[slot.slot_status] ?? 'bg-gray-100 text-gray-500'}`}
                      >
                        {slot.ig_content_library?.title ?? slot.slot_window}
                      </div>
                    ))}
                    {daySlots.length > 2 && (
                      <p className="text-[10px] text-slate-400">+{daySlots.length - 2} more</p>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Day detail on click */}
        {selected && (
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">
              {format(selected, 'EEEE, MMMM d')} — {selectedSlots.length} slot{selectedSlots.length !== 1 ? 's' : ''}
            </h3>
            {selectedSlots.length === 0 ? (
              <p className="text-sm text-slate-400">No slots on this day.</p>
            ) : (
              <div className="space-y-2">
                {selectedSlots.map((slot) => (
                  <div key={slot.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
                    <div className="text-xs text-slate-500 font-mono w-16 shrink-0 capitalize">{slot.slot_window}</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {slot.ig_content_library?.title ?? 'Empty'}
                      </p>
                      {slot.ig_content_library?.media_type && (
                        <p className="text-xs text-slate-400">{slot.ig_content_library.media_type}</p>
                      )}
                    </div>
                    <SlotBadge status={slot.slot_status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Upcoming slots table */}
        <div className="card p-5">
          <h2 className="text-base font-semibold text-slate-900 mb-4">Upcoming Slots (next 50)</h2>

          {loading && (
            <div className="flex items-center justify-center gap-2 text-slate-400 py-10">
              <div className="w-4 h-4 border-2 border-violet-300 border-t-violet-600 rounded-full animate-spin" />
              <span className="text-sm">Loading slots…</span>
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
              Error loading slots: {error}
            </div>
          )}

          {!loading && !error && upcomingSlots.length === 0 && (
            <p className="text-sm text-slate-400 py-10 text-center">No upcoming slots found.</p>
          )}

          {!loading && !error && upcomingSlots.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left text-xs font-medium text-slate-400 pb-2 pr-4">Date</th>
                    <th className="text-left text-xs font-medium text-slate-400 pb-2 pr-4">Window</th>
                    <th className="text-left text-xs font-medium text-slate-400 pb-2 pr-4">Scheduled (ET)</th>
                    <th className="text-left text-xs font-medium text-slate-400 pb-2 pr-4">Status</th>
                    <th className="text-left text-xs font-medium text-slate-400 pb-2 pr-4">Content</th>
                    <th className="text-left text-xs font-medium text-slate-400 pb-2">Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {upcomingSlots.map((slot) => (
                    <tr key={slot.id} className="hover:bg-gray-50 transition-colors">
                      <td className="py-2.5 pr-4 font-mono text-xs text-slate-600">{slot.slot_date}</td>
                      <td className="py-2.5 pr-4 text-xs text-slate-600 capitalize">{slot.slot_window}</td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-slate-600 whitespace-nowrap">{formatNY(slot.scheduled_at)}</td>
                      <td className="py-2.5 pr-4"><SlotBadge status={slot.slot_status} /></td>
                      <td className="py-2.5 pr-4 text-xs text-slate-700 max-w-xs truncate">
                        {slot.ig_content_library?.title ?? <span className="text-slate-400 italic">Empty</span>}
                      </td>
                      <td className="py-2.5 text-xs text-slate-500">{slot.ig_content_library?.media_type ?? '—'}</td>
                    </tr>
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
