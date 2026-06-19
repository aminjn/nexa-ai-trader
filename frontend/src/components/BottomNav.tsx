import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'

interface NavItem { path: string; label: string; icon: any }

/** منوی پایینِ موبایل + کشوی «بیشتر» برای بقیهٔ آیتم‌ها */
export default function BottomNav({ items }: { items: NavItem[] }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)

  const isActive = (p: string) => location.pathname === p || location.pathname.startsWith(p + '/')

  // آیتم‌های اصلی نوار پایین (بقیه در «بیشتر»)
  const primaryPaths = ['/dashboard', '/wallet', '/signals', '/profile']
  const primary: NavItem[] = primaryPaths
    .map(p => items.find(i => i.path === p))
    .filter(Boolean) as NavItem[]
  const go = (p: string) => { setMoreOpen(false); navigate(p) }

  const tab = (path: string, label: string, Icon: any, onClick: () => void, active: boolean) => (
    <button key={path} onClick={onClick} style={{
      flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
      background: 'transparent', border: 'none', cursor: 'pointer', padding: '6px 2px',
      color: active ? 'var(--accent)' : 'var(--dim)', fontFamily: 'inherit', fontSize: 10, fontWeight: 600,
    }}>
      <Icon size={21} />
      <span style={{ whiteSpace: 'nowrap' }}>{label}</span>
    </button>
  )

  return (
    <>
      {/* کشوی «بیشتر» */}
      {moreOpen && (
        <div onClick={() => setMoreOpen(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 60 }}>
          <div onClick={e => e.stopPropagation()} style={{
            position: 'fixed', insetInlineStart: 0, insetInlineEnd: 0, bottom: 64, background: 'var(--panel)',
            borderTop: '1px solid var(--border2)', borderRadius: '18px 18px 0 0', padding: 16, zIndex: 61,
            maxHeight: '60vh', overflowY: 'auto',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontWeight: 700 }}>همهٔ بخش‌ها</span>
              <button onClick={() => setMoreOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--dim)', cursor: 'pointer' }}><X size={20} /></button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
              {items.map(({ path, label, icon: Icon }) => (
                <button key={path} onClick={() => go(path)} style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, padding: '16px 8px',
                  borderRadius: 14, border: '1px solid var(--border)', cursor: 'pointer', fontFamily: 'inherit',
                  background: isActive(path) ? 'color-mix(in srgb,var(--accent) 12%,transparent)' : 'var(--bg2)',
                  color: isActive(path) ? 'var(--accent)' : 'var(--text)', fontSize: 12, fontWeight: 600,
                }}>
                  <Icon size={22} />
                  <span style={{ textAlign: 'center' }}>{label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* نوار پایین */}
      <nav style={{
        position: 'fixed', insetInlineStart: 0, insetInlineEnd: 0, bottom: 0, height: 64,
        background: 'color-mix(in srgb,var(--bg2) 92%,var(--bg))', backdropFilter: 'blur(14px)',
        borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center',
        zIndex: 50, paddingBottom: 'env(safe-area-inset-bottom)',
      }}>
        {primary.map(it => tab(it.path, it.label, it.icon, () => go(it.path), isActive(it.path)))}
        {tab('more', 'بیشتر', Menu, () => setMoreOpen(o => !o), moreOpen)}
      </nav>
    </>
  )
}
