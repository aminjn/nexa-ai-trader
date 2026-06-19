import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAppStore } from './stores/appStore'
import { useAuthStore } from './stores/authStore'
import api from './lib/api'

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
import Signals from './pages/Signals'
import Plans from './pages/Plans'
import TradingPlansAdmin from './pages/TradingPlansAdmin'
import Profile from './pages/Profile'
import Wallet from './pages/Wallet'
import AdminWallet from './pages/AdminWallet'
import Notifications from './pages/Notifications'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/" replace />
  return <>{children}</>
}

// دروازه‌بانی: ابتدا احراز هویت، سپس اشتراک فعال (سوپر ادمین مستثناست)
function PlanGate({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isSuperAdmin } = useAuthStore()
  const [state, setState] = useState<'loading' | 'ok' | 'noplan' | 'nokyc'>('loading')
  useEffect(() => {
    if (!isAuthenticated) return
    if (isSuperAdmin) { setState('ok'); return }
    api.get('/trading/my-access')
      .then(r => {
        if (r.data?.kyc_status !== 'verified') setState('nokyc')
        else if (r.data?.has_access) setState('ok')
        else setState('noplan')
      })
      .catch(() => setState('noplan'))
  }, [isAuthenticated, isSuperAdmin])
  if (!isAuthenticated) return <Navigate to="/" replace />
  if (state === 'loading') return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--dim)' }}>در حال بارگذاری…</div>
  if (state === 'nokyc') return <Navigate to="/profile" replace />
  if (state === 'noplan') return <Navigate to="/plans" replace />
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
          <Route path="/plans" element={<ProtectedRoute><Plans /></ProtectedRoute>} />
          <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
          <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
          <Route path="/wallet" element={<ProtectedRoute><Wallet /></ProtectedRoute>} />
          <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><PlanGate><Dashboard /></PlanGate></ProtectedRoute>} />
          <Route path="/model" element={<AdminRoute><Model /></AdminRoute>} />
          <Route path="/strategy" element={<ProtectedRoute><PlanGate><Strategy /></PlanGate></ProtectedRoute>} />
          <Route path="/short" element={<ProtectedRoute><PlanGate><Short /></PlanGate></ProtectedRoute>} />
          <Route path="/exchanges" element={<ProtectedRoute><PlanGate><Exchanges /></PlanGate></ProtectedRoute>} />
          <Route path="/history" element={<ProtectedRoute><PlanGate><History /></PlanGate></ProtectedRoute>} />
          <Route path="/ai" element={<ProtectedRoute><PlanGate><AI /></PlanGate></ProtectedRoute>} />
          <Route path="/signals" element={<ProtectedRoute><PlanGate><Signals /></PlanGate></ProtectedRoute>} />
          <Route path="/subscription" element={<ProtectedRoute><PlanGate><Signals /></PlanGate></ProtectedRoute>} />
          <Route path="/admin" element={<AdminRoute><SuperAdmin /></AdminRoute>} />
          <Route path="/admin/users/:id" element={<AdminRoute><UserDetail /></AdminRoute>} />
          <Route path="/admin/trading-plans" element={<AdminRoute><TradingPlansAdmin /></AdminRoute>} />
          <Route path="/admin/wallet" element={<AdminRoute><AdminWallet /></AdminRoute>} />
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
