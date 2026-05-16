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
import StatusPill from '../components/StatusPill'
import type { QueueItem } from '../lib/types'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export default function CalendarPage() {
  const [current, setCurrent] = useState(new Date())
  const [events, setEvents] = useState<QueueItem[]>([])
  const [selected, setSelected] = useState<Date | null>(null)

  useEffect(() => {
    async function load() {
      const start = startOfMonth(current).toISOString()
      const end = endOfMonth(current).toISOString()
      const { data } = await supabase
        .from('ig_publishing_queue')
        .select('*, ig_content_library(id, title)')
        .gte('scheduled_at', start)
        .lte('scheduled_at', end)
        .not('scheduled_at', 'is', null)
        .order('scheduled_at', { ascending: true })
      setEvents((data ?? []) as QueueItem[])
    }
    load()
  }, [current])

  const monthStart = startOfMonth(current)
  const days = eachDayOfInterval({ start: monthStart, end: endOfMonth(current) })
  const startPad = getDay(monthStart)
  const paddingDays = Array.from({ length: startPad })

  function eventsForDay(day: Date) {
    return events.filter((e) => e.scheduled_at && isSameDay(new Date(e.scheduled_at), day))
  }

  const selectedEvents = selected ? eventsForDay(selected) : []

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Calendar</h1>
        <p className="page-subtitle">Scheduled posts — {format(current, 'MMMM yyyy')}</p>
      </div>

      <div className="page-body space-y-4">
        <div className="card p-5">
          {/* Month navigation */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-slate-900">{format(current, 'MMMM yyyy')}</h2>
            <div className="flex gap-1">
              <button
                onClick={() => setCurrent(subMonths(current, 1))}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-slate-600 transition-colors"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                onClick={() => setCurrent(new Date())}
                className="px-2.5 py-1 rounded-lg hover:bg-gray-100 text-xs text-slate-600 font-medium transition-colors"
              >
                Today
              </button>
              <button
                onClick={() => setCurrent(addMonths(current, 1))}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-slate-600 transition-colors"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          {/* Weekday headers */}
          <div className="grid grid-cols-7 gap-1 mb-1">
            {WEEKDAYS.map((d) => (
              <div key={d} className="text-center text-xs font-medium text-slate-400 py-1">{d}</div>
            ))}
          </div>

          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-1">
            {paddingDays.map((_, i) => (
              <div key={`pad-${i}`} className="h-20 rounded-lg" />
            ))}
            {days.map((day) => {
              const dayEvents = eventsForDay(day)
              const isSelected = selected && isSameDay(day, selected)
              return (
                <button
                  key={day.toISOString()}
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
                    {dayEvents.slice(0, 2).map((ev) => (
                      <div
                        key={ev.id}
                        className={[
                          'text-[10px] rounded px-1 py-0.5 truncate font-medium',
                          ev.queue_status === 'published' ? 'bg-emerald-100 text-emerald-700' :
                          ev.queue_status === 'failed' ? 'bg-red-100 text-red-700' :
                          'bg-blue-100 text-blue-700',
                        ].join(' ')}
                      >
                        {ev.ig_content_library?.title ?? '—'}
                      </div>
                    ))}
                    {dayEvents.length > 2 && (
                      <p className="text-[10px] text-slate-400">+{dayEvents.length - 2} more</p>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Selected day detail */}
        {selected && (
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-3">
              {format(selected, 'EEEE, MMMM d')} — {selectedEvents.length} post{selectedEvents.length !== 1 ? 's' : ''}
            </h3>
            {selectedEvents.length === 0 ? (
              <p className="text-sm text-slate-400">No posts scheduled on this day.</p>
            ) : (
              <div className="space-y-2">
                {selectedEvents.map((ev) => (
                  <div key={ev.id} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
                    <div className="text-xs text-slate-500 font-mono w-12 shrink-0">
                      {ev.scheduled_at ? format(new Date(ev.scheduled_at), 'HH:mm') : '—'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">
                        {ev.ig_content_library?.title ?? ev.content_id.slice(0, 8)}
                      </p>
                    </div>
                    <StatusPill status={ev.queue_status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
