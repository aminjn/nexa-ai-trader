import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAppStore } from './stores/appStore'
import { useAuthStore } from './stores/authStore'

// Pages (lazy-loadable in production)
import Auth from './pages/Auth'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Model from './pages/Model'
import Strategy from './pages/Strategy'
import Short from './pages/Short'
import Exchanges from './pages/Exchanges'
import History from './pages/History'
import AI from './pages/AI'
import SuperAdmin from './pages/SuperAdmin'
import UserDetail from './pages/UserDetail'
import AdminSettings from './pages/AdminSettings'
import Scraper from './pages/Scraper'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/" replace />
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isSuperAdmin } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/" replace />
  if (!isSuperAdmin) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

export default function App() {
  const { theme, lang, dir } = useAppStore()

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.lang = lang
    document.documentElement.dir = dir
  }, [theme, lang, dir])

  return (
    <div data-theme={theme} dir={dir} style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Auth />} />
          <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/model" element={<ProtectedRoute><Model /></ProtectedRoute>} />
          <Route path="/strategy" element={<ProtectedRoute><Strategy /></ProtectedRoute>} />
          <Route path="/short" element={<ProtectedRoute><Short /></ProtectedRoute>} />
          <Route path="/exchanges" element={<ProtectedRoute><Exchanges /></ProtectedRoute>} />
          <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
          <Route path="/ai" element={<ProtectedRoute><AI /></ProtectedRoute>} />
          <Route path="/admin" element={<AdminRoute><SuperAdmin /></AdminRoute>} />
          <Route path="/admin/users/:id" element={<AdminRoute><UserDetail /></AdminRoute>} />
          <Route path="/scraper" element={<AdminRoute><Scraper /></AdminRoute>} />
          <Route path="/settings" element={<AdminRoute><AdminSettings /></AdminRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster
        position="top-center"
        toastOptions={{
          style: {
            background: 'var(--bg2)',
            color: 'var(--text)',
            border: '1px solid var(--border2)',
            fontFamily: 'Vazirmatn, sans-serif',
          },
        }}
      />
    </div>
  )
}
