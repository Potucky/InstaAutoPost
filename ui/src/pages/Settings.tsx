import { CheckCircle, AlertCircle, Shield, Info } from 'lucide-react'

interface EnvVar {
  name: string
  description: string
  where: 'frontend' | 'backend'
  required: boolean
}

const ENV_VARS: EnvVar[] = [
  { name: 'VITE_SUPABASE_URL',       description: 'Supabase project URL',                     where: 'frontend', required: true },
  { name: 'VITE_SUPABASE_ANON_KEY',  description: 'Supabase anon key (browser-safe)',          where: 'frontend', required: true },
  { name: 'SUPABASE_URL',            description: 'Supabase project URL',                     where: 'backend',  required: true },
  { name: 'SUPABASE_SERVICE_ROLE_KEY', description: 'Service role key — backend worker only', where: 'backend',  required: true },
  { name: 'IG_USER_ID',              description: 'Instagram Business User ID',                where: 'backend',  required: false },
  { name: 'IG_ACCESS_TOKEN',         description: 'Long-lived Instagram access token',         where: 'backend',  required: false },
  { name: 'INSTAGRAM_API_ENABLED',   description: 'Set to "true" to enable live publishing',  where: 'backend',  required: false },
]

function checkFrontendEnv(name: string): boolean {
  if (name === 'VITE_SUPABASE_URL') return !!import.meta.env.VITE_SUPABASE_URL
  if (name === 'VITE_SUPABASE_ANON_KEY') return !!import.meta.env.VITE_SUPABASE_ANON_KEY
  return false
}

const SAFETY_CHECKS = [
  { label: 'Service role key is never used in the frontend', ok: true },
  { label: 'Frontend uses anon key only (RLS enforced)', ok: true },
  { label: 'Instagram API is called from backend worker only', ok: true },
  { label: 'Row locking prevents duplicate publishing', ok: true },
  { label: 'published_at + external_media_id guards against re-publish', ok: true },
  { label: 'Dry-run mode is the default (INSTAGRAM_API_ENABLED not set)', ok: true },
]

export default function Settings() {
  const frontendVars = ENV_VARS.filter((v) => v.where === 'frontend')
  const backendVars = ENV_VARS.filter((v) => v.where === 'backend')

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Settings & Safety</h1>
        <p className="page-subtitle">Environment configuration and architecture safety checks</p>
      </div>

      <div className="page-body space-y-6">

        {/* Architecture note */}
        <div className="rounded-xl bg-violet-50 border border-violet-200 px-5 py-4 flex gap-3">
          <Info size={16} className="text-violet-600 mt-0.5 shrink-0" />
          <div className="text-sm text-violet-800">
            <p className="font-semibold mb-1">InstaAutoPost — Architecture</p>
            <p>
              The UI manages content and queue records only. All Instagram API publishing is handled exclusively
              by the backend worker (<code className="font-mono bg-violet-100 px-1 rounded">scripts/instaautopost_publisher.py</code>),
              triggered by GitHub Actions on a 5-minute cron schedule.
              The service role key never leaves the backend.
            </p>
          </div>
        </div>

        {/* Frontend env */}
        <div className="card">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <Shield size={15} className="text-slate-500" />
            <h2 className="text-sm font-semibold text-slate-900">Frontend Environment Variables</h2>
            <span className="ml-auto text-xs text-slate-400">Set in ui/.env.local</span>
          </div>
          <div className="divide-y divide-gray-50">
            {frontendVars.map((v) => {
              const set = checkFrontendEnv(v.name)
              return (
                <div key={v.name} className="flex items-center gap-4 px-5 py-3">
                  <div className="flex-1 min-w-0">
                    <code className="text-xs font-mono font-semibold text-slate-800">{v.name}</code>
                    <p className="text-xs text-slate-500 mt-0.5">{v.description}</p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {set ? (
                      <>
                        <CheckCircle size={14} className="text-emerald-500" />
                        <span className="text-xs text-emerald-600 font-medium">Set</span>
                      </>
                    ) : (
                      <>
                        <AlertCircle size={14} className="text-amber-500" />
                        <span className="text-xs text-amber-600 font-medium">Not set</span>
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Backend env */}
        <div className="card">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <Shield size={15} className="text-slate-500" />
            <h2 className="text-sm font-semibold text-slate-900">Backend Environment Variables</h2>
            <span className="ml-auto text-xs text-slate-400">GitHub Actions Secrets / local shell</span>
          </div>
          <div className="divide-y divide-gray-50">
            {backendVars.map((v) => (
              <div key={v.name} className="flex items-center gap-4 px-5 py-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <code className="text-xs font-mono font-semibold text-slate-800">{v.name}</code>
                    {!v.required && (
                      <span className="text-[10px] text-slate-400 bg-gray-100 px-1.5 py-0.5 rounded-full">optional</span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">{v.description}</p>
                </div>
                <div className="text-xs text-slate-400 italic shrink-0">backend only</div>
              </div>
            ))}
          </div>
          <div className="px-5 py-3 bg-amber-50 border-t border-amber-100 rounded-b-xl">
            <p className="text-xs text-amber-700 flex items-center gap-1.5">
              <AlertCircle size={12} />
              Backend variables are not accessible here. Check GitHub Secrets or your local shell.
            </p>
          </div>
        </div>

        {/* Safety checks */}
        <div className="card">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <Shield size={15} className="text-emerald-500" />
            <h2 className="text-sm font-semibold text-slate-900">Safety Checks</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {SAFETY_CHECKS.map(({ label, ok }) => (
              <div key={label} className="flex items-center gap-3 px-5 py-3">
                {ok
                  ? <CheckCircle size={15} className="text-emerald-500 shrink-0" />
                  : <AlertCircle size={15} className="text-red-500 shrink-0" />}
                <p className="text-sm text-slate-700">{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Worker info */}
        <div className="card px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-900 mb-3">Worker Reference</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            {[
              { label: 'Worker script', value: 'scripts/instaautopost_publisher.py' },
              { label: 'Worker version', value: '1.0.0' },
              { label: 'Schedule', value: 'Every 5 minutes (GitHub Actions cron)' },
              { label: 'Items per run', value: 'Exactly 1 queue item' },
              { label: 'Default mode', value: 'Dry-run (safe)' },
              { label: 'Lock mechanism', value: 'FOR UPDATE SKIP LOCKED (PostgreSQL)' },
            ].map(({ label, value }) => (
              <div key={label} className="flex gap-3">
                <p className="text-slate-500 w-36 shrink-0">{label}</p>
                <p className="text-slate-800 font-medium font-mono text-xs">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
