import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Zap } from 'lucide-react'
import { supabase } from '../lib/supabase'
import { useAuth } from '../lib/auth'

const enableSignup = import.meta.env.VITE_ENABLE_SIGNUP === 'true'

export default function LoginPage() {
  const { session, loading } = useAuth()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  if (loading) return <div className="min-h-screen bg-slate-900" />
  if (session) return <Navigate to="/dashboard" replace />

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setInfo(null)

    if (mode === 'signin') {
      const { error: err } = await supabase.auth.signInWithPassword({ email, password })
      if (err) setError(err.message)
    } else if (enableSignup) {
      const { error: err } = await supabase.auth.signUp({ email, password })
      if (err) setError(err.message)
      else setInfo('Check your email for a confirmation link, then sign in.')
    }

    setSubmitting(false)
  }

  function switchMode() {
    setMode(mode === 'signin' ? 'signup' : 'signin')
    setError(null)
    setInfo(null)
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3 justify-center mb-8">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center">
            <Zap size={16} className="text-white" />
          </div>
          <div>
            <p className="text-white font-bold text-lg leading-tight">InstaAutoPost</p>
            <p className="text-slate-500 text-xs">Control Center</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-6">
          <h1 className="text-lg font-bold text-slate-900 mb-5">
            {enableSignup && mode === 'signup' ? 'Create account' : 'Sign in'}
          </h1>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label" htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label className="label" htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                minLength={6}
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {info && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">
                {info}
              </div>
            )}

            <button type="submit" className="btn-primary w-full justify-center" disabled={submitting}>
              {submitting ? 'Please wait...' : enableSignup && mode === 'signup' ? 'Create account' : 'Sign in'}
            </button>
          </form>

          {enableSignup ? (
            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={switchMode}
                className="text-sm text-violet-600 hover:text-violet-700"
              >
                {mode === 'signin'
                  ? "Don't have an account? Sign up"
                  : 'Already have an account? Sign in'}
              </button>
            </div>
          ) : (
            <p className="mt-4 text-center text-xs text-slate-400">
              Sign up is disabled for this production control panel.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
