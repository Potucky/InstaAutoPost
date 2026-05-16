import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Library,
  Upload,
  ListOrdered,
  Calendar,
  ClipboardList,
  Settings,
  Zap,
  LogOut,
} from 'lucide-react'
import { useAuth } from '../lib/auth'
import { supabase } from '../lib/supabase'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/content',   icon: Library,         label: 'Content Library' },
  { to: '/upload',    icon: Upload,           label: 'Upload Video' },
  { to: '/queue',     icon: ListOrdered,      label: 'Publishing Queue' },
  { to: '/calendar',  icon: Calendar,         label: 'Calendar' },
  { to: '/logs',      icon: ClipboardList,    label: 'Logs & Attempts' },
  { to: '/settings',  icon: Settings,         label: 'Settings' },
]

export default function Sidebar() {
  const { user } = useAuth()

  return (
    <aside className="w-60 shrink-0 bg-slate-900 flex flex-col h-screen sticky top-0">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-pink-500 flex items-center justify-center shrink-0">
            <Zap size={14} className="text-white" />
          </div>
          <div>
            <p className="text-white font-semibold text-sm leading-tight">InstaAutoPost</p>
            <p className="text-slate-500 text-xs leading-tight">Control Center</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all',
                isActive
                  ? 'bg-violet-600 text-white font-medium'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800',
              ].join(' ')
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer — user + sign out */}
      <div className="px-3 py-4 border-t border-slate-800">
        {user && (
          <div className="mb-3">
            <p className="text-slate-400 text-xs truncate px-2 mb-1" title={user.email ?? ''}>
              {user.email}
            </p>
            <button
              type="button"
              onClick={() => supabase.auth.signOut()}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-slate-500 hover:text-red-400 hover:bg-slate-800 transition-colors"
            >
              <LogOut size={13} />
              Sign out
            </button>
          </div>
        )}
        <p className="text-slate-600 text-xs px-2">v0.1.0</p>
      </div>
    </aside>
  )
}
