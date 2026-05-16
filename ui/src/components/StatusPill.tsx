interface Config {
  bg: string
  text: string
  dot: string
  label: string
}

const STATUS_CONFIG: Record<string, Config> = {
  draft:           { bg: 'bg-gray-100',    text: 'text-gray-600',    dot: 'bg-gray-400',    label: 'Draft' },
  approved:        { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500', label: 'Approved' },
  archived:        { bg: 'bg-gray-100',    text: 'text-gray-500',    dot: 'bg-gray-300',    label: 'Archived' },
  scheduled:       { bg: 'bg-blue-100',    text: 'text-blue-700',    dot: 'bg-blue-500',    label: 'Scheduled' },
  ready:           { bg: 'bg-indigo-100',  text: 'text-indigo-700',  dot: 'bg-indigo-500',  label: 'Ready' },
  processing:      { bg: 'bg-amber-100',   text: 'text-amber-700',   dot: 'bg-amber-500',   label: 'Processing' },
  published:       { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500', label: 'Published' },
  failed:          { bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500',     label: 'Failed' },
  cancelled:       { bg: 'bg-gray-100',    text: 'text-gray-500',    dot: 'bg-gray-300',    label: 'Cancelled' },
  retry_scheduled: { bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500',  label: 'Retry' },
  success:         { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500', label: 'Success' },
  dry_run:         { bg: 'bg-violet-100',  text: 'text-violet-700',  dot: 'bg-violet-400',  label: 'Dry Run' },
}

const FALLBACK: Config = { bg: 'bg-gray-100', text: 'text-gray-600', dot: 'bg-gray-400', label: '' }

interface Props {
  status: string
  showDot?: boolean
}

export default function StatusPill({ status, showDot = true }: Props) {
  const c = STATUS_CONFIG[status] ?? { ...FALLBACK, label: status }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${c.bg} ${c.text}`}>
      {showDot && <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />}
      {c.label}
    </span>
  )
}
