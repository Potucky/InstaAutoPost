// Removed: banner had no real signal — it hardcoded "workflow disabled" regardless of actual
// GitHub Actions state. Workflow is active (cron */5 * * * *). Remove this import from callers.
export default function WorkflowDisabledBanner() {
  return null
}
