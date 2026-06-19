import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { LayoutDashboard, Brain, TrendingUp, TrendingDown, Building2, History, Sparkles, Shield, Settings, LogOut, Sun, Moon, Globe, Radio, CreditCard, Wallet, UserCircle, Bell, Power } from 'lucide-react'
import { useAppStore } from '../stores/appStore'
import { useAuthStore } from '../stores/authStore'
import NotificationBell from './NotificationBell'
import BottomNav from './BottomNav'
import { useIsMobile } from '../hooks/useIsMobile'
import Logo from './Logo'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface LayoutProps { children: React.ReactNode; title: string; subtitle?: string }

export default function Layout({ children, title, subtitle }: LayoutProps) {
  const { t, theme, lang, dir, toggleTheme } = useAppStore()
  const { fullName, isSuperAdmin, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [equity, setEquity] = useState('0.00')
  const [botActive, setBotActive] = useState(false)

  const navItems = [
    { path: '/dashboard', label: t.navDashboard, icon: LayoutDashboard },
    { path: '/strategy', label: t.navStrategy, icon: TrendingUp },
    { path: '/short', label: t.navShort, icon: TrendingDown },
    { path: '/exchanges', label: t.navExchanges, icon: Building2 },
    { path: '/history', label: t.navHistory, icon: History },
    { path: '/ai', label: t.navAI, icon: Sparkles },
    { path: '/signals', label: 'سیگنال‌ها', icon: Radio },
    { path: '/wallet', label: 'کیف پول', icon: Wallet },
    { path: '/notifications', label: 'اعلان‌ها', icon: Bell },
    { path: '/plans', label: 'پلن‌ها', icon: CreditCard },
    { path: '/profile', label: 'پروفایل', icon: UserCircle },
    ...(isSuperAdmin ? [
      { path: '/model', label: t.navModel, icon: Brain },
      { path: '/admin/trading-plans', label: 'پلن‌های ربات', icon: CreditCard },
      { path: '/admin/wallet', label: 'واریز و احراز هویت', icon: Wallet },
      { path: '/scraper', label: 'اسکرپر', icon: Globe },
      { path: '/admin', label: t.navAdmin, icon: Shield },
      { path: '/settings', label: t.navSettings, icon: Settings },
    ] : []),
  ]

  useEffect(() => {
    api.get('/dashboard/stats').then(r => {
      setEquity(Math.round(r.data.total_equity ?? 0).toLocaleString('fa-IR'))
      setBotActive(r.data.bot_active ?? false)
    }).catch(() => {})
  }, [location.pathname])

  const toggleBot = async () => {
    try {
      const r = await api.post('/strategy/bot/toggle')
      setBotActive(r.data.bot_active)
      toast.success(r.data.bot_active ? 'ربات فعال شد' : 'ربات متوقف شد')
    } catch { toast.error('خطا در تغییر وضعیت ربات') }
  }

  const accentBg = 'linear-gradient(135deg, var(--accent), var(--accent2))'
  const initials = fullName?.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || 'U'
  const isMobile = useIsMobile()

  return (
    <div style={{ display: 'flex', minHeight: '100vh', position: 'relative', overflow: 'hidden' }}>
      {/* Grid background */}
      <div style={{ position: 'fixed', inset: 0, pointerEvents: 'none',
        backgroundImage: 'linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px)',
        backgroundSize: '48px 48px', animation: 'gridmove 14s linear infinite', zIndex: 0 }} />
      {/* Blobs */}
      <div style={{ position: 'fixed', top: -140, insetInlineStart: -90, width: 560, height: 560, borderRadius: '50%',
        background: 'radial-gradient(circle,var(--accent) 0%,transparent 70%)', opacity: .18, filter: 'blur(48px)', pointerEvents: 'none', zIndex: 0 }} />
      <div style={{ position: 'fixed', bottom: -180, insetInlineEnd: -90, width: 540, height: 540, borderRadius: '50%',
        background: 'radial-gradient(circle,var(--accent2) 0%,transparent 70%)', opacity: .15, filter: 'blur(48px)', pointerEvents: 'none', zIndex: 0 }} />

      {/* Sidebar (در موبایل مخفی؛ به‌جایش منوی پایین) */}
      {!isMobile && (
      <aside style={{ width: 248, flexShrink: 0, background: 'var(--sidebar-bg)', borderInlineEnd: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', padding: '22px 16px', position: 'sticky', top: 0, height: '100vh', zIndex: 10 }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '0 8px 22px', borderBottom: '1px solid var(--border)', marginBottom: 16 }}>
          <Logo size={36} />
          <div>
            <div style={{ fontFamily: "'Space Grotesk'", fontWeight: 700, fontSize: 17, letterSpacing: '.03em' }}>{t.brand}</div>
            <div style={{ fontSize: 11, color: 'var(--accent)', fontFamily: "'JetBrains Mono'" }}>{t.versionTag}</div>
          </div>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
          {navItems.map(({ path, label, icon: Icon }) => {
            const active = location.pathname === path || location.pathname.startsWith(path + '/')
            return (
              <button key={path} onClick={() => navigate(path)} style={{
                display: 'flex', alignItems: 'center', gap: 13, padding: '11px 13px',
                border: 'none', borderRadius: 11, cursor: 'pointer', fontFamily: 'inherit', fontSize: 14, fontWeight: 500,
                textAlign: 'start', background: active ? 'color-mix(in srgb,var(--accent) 12%,transparent)' : 'transparent',
                color: active ? 'var(--accent)' : 'var(--dim)', transition: '.18s', position: 'relative',
              }}>
                {active && <span style={{ position: 'absolute', insetInlineStart: 0, top: '50%', transform: 'translateY(-50%)', width: 3, height: 18, borderRadius: 3, background: 'var(--accent)' }} />}
                <Icon size={18} />
                {label}
              </button>
            )
          })}
        </nav>

        {/* User card */}
        <div style={{ padding: 14, border: '1px solid var(--border)', borderRadius: 14, background: 'var(--bg3)' }}>
          <div onClick={() => navigate('/profile')} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, cursor: 'pointer' }} title="پروفایل">
            <div style={{ width: 32, height: 32, borderRadius: '50%', background: accentBg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: '#05121a', fontSize: 13 }}>{initials}</div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{fullName}</div>
              <div style={{ fontSize: 11, color: 'var(--dim)' }}>{isSuperAdmin ? '⭐ مدیر کل' : 'کاربر'}</div>
            </div>
          </div>
          <button onClick={() => { logout(); navigate('/') }} style={{ width: '100%', padding: 9, border: '1px solid var(--border2)', borderRadius: 9, background: 'transparent', color: 'var(--dim)', fontSize: 13, fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <LogOut size={13} /> {t.logout}
          </button>
        </div>
      </aside>
      )}

      {/* Main */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', position: 'relative', zIndex: 1 }}>
        {/* Header */}
        <header style={{ height: isMobile ? 60 : 72, flexShrink: 0, borderBottom: '1px solid var(--border)', background: 'color-mix(in srgb,var(--bg2) 70%,transparent)', backdropFilter: 'blur(12px)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: isMobile ? 'env(safe-area-inset-top) max(14px, env(safe-area-inset-right)) 0 max(14px, env(safe-area-inset-left))' : '0 28px', position: 'sticky', top: 0, zIndex: 5, boxSizing: 'content-box' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            {isMobile && <Logo size={28} />}
            <div style={{ minWidth: 0 }}>
              <div style={{ fontFamily: "'Space Grotesk'", fontSize: isMobile ? 16 : 20, fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{title}</div>
              {subtitle && !isMobile && <div style={{ fontSize: 12, color: 'var(--dim)' }}>{subtitle}</div>}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 8 : 12 }}>
            {!isMobile && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 12 }}>
                <span style={{ fontSize: 11, color: 'var(--dim)' }}>{t.totalEquity}</span>
                <span style={{ fontFamily: "'JetBrains Mono'", fontWeight: 700, fontSize: 15 }}>{equity} ت</span>
              </div>
            )}
            <button onClick={toggleBot} title={botActive ? t.botRunning : t.botStopped} style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 6 : 9, padding: isMobile ? '8px 12px' : '10px 16px', border: `1.5px solid ${botActive ? 'var(--green)' : 'var(--red)'}`, borderRadius: 12, background: botActive ? 'color-mix(in srgb,var(--green) 14%,transparent)' : 'color-mix(in srgb,var(--red) 12%,transparent)', color: botActive ? 'var(--green)' : 'var(--red)', cursor: 'pointer', fontFamily: 'inherit', fontWeight: 700, fontSize: 13, transition: '.2s', flexShrink: 0 }}>
              <Power size={16} />
              {botActive ? (isMobile ? 'روشن' : t.botRunning) : (isMobile ? 'خاموش' : t.botStopped)}
            </button>
            <NotificationBell />
            <button onClick={toggleTheme} style={{ background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text)', width: 40, height: 38, borderRadius: 11, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </header>

        <main style={{ flex: 1, padding: isMobile ? '16px 14px' : 28, overflowY: 'auto', paddingBottom: isMobile ? 'calc(64px + env(safe-area-inset-bottom) + 16px)' : 28 }}>
          {children}
        </main>
      </div>

      {isMobile && <BottomNav items={navItems} />}
    </div>
  )
}
