import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './lib/auth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import ContentLibrary from './pages/ContentLibrary'
import UploadVideo from './pages/UploadVideo'
import PublishingQueue from './pages/PublishingQueue'
import CalendarPage from './pages/CalendarPage'
import LogsAttempts from './pages/LogsAttempts'
import Settings from './pages/Settings'

function RequireAuth() {
  const { session, loading } = useAuth()
  const location = useLocation()
  if (loading) return <div className="min-h-screen bg-slate-900" />
  if (!session) return <Navigate to="/login" state={{ from: location }} replace />
  return <Outlet />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="content" element={<ContentLibrary />} />
          <Route path="upload" element={<UploadVideo />} />
          <Route path="queue" element={<PublishingQueue />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="logs" element={<LogsAttempts />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
