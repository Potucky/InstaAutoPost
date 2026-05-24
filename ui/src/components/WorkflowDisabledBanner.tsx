import { useState } from 'react'
import { AlertCircle } from 'lucide-react'

const STORAGE_KEY = 'workflow_banner_dismissed'

function isDismissed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true'
  } catch {
    return false
  }
}

export default function WorkflowDisabledBanner() {
  const [dismissed, setDismissed] = useState(isDismissed)

  if (dismissed) return null

  function dismiss() {
    try {
      localStorage.setItem(STORAGE_KEY, 'true')
    } catch {
      // localStorage unavailable — dismiss in memory only
    }
    setDismissed(true)
  }

  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800">
      <AlertCircle size={16} className="mt-0.5 shrink-0 text-amber-500" />
      <p className="flex-1 text-sm">
        Publisher workflow is currently disabled in GitHub Actions. Items marked Ready will not be
        published automatically until the workflow is re-enabled in GitHub.
      </p>
      <button
        onClick={dismiss}
        aria-label="Dismiss"
        className="ml-2 shrink-0 text-amber-500 hover:text-amber-700 font-medium leading-none"
      >
        ×
      </button>
    </div>
  )
}
