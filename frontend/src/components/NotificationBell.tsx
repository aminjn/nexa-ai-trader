import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import api from '../lib/api'

interface Notif { id: number; type: string; title: string; message: string; link: string; read: boolean; created_at: string | null }

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<Notif[]>([])
  const [unread, setUnread] = useState(0)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    try { const r = await api.get('/notifications/'); setItems(r.data.items || []); setUnread(r.data.unread || 0) } catch { /* ignore */ }
  }, [])

  useEffect(() => { load(); const id = setInterval(load, 20000); return () => clearInterval(id) }, [load])
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])

  const toggle = async () => {
    const next = !open; setOpen(next)
    if (next && unread > 0) { try { await api.post('/notifications/read-all'); setUnread(0) } catch { /* ignore */ } }
  }
  const click = (n: Notif) => { setOpen(false); if (n.link) navigate(n.link) }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={toggle} style={{ position: 'relative', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--text)' }}>
        <Bell size={18} />
        {unread > 0 && (
          <span style={{ position: 'absolute', top: -4, insetInlineEnd: -4, minWidth: 18, height: 18, padding: '0 4px', borderRadius: 9, background: 'var(--red)', color: '#fff', fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div style={{ position: 'absolute', insetInlineEnd: 0, top: 48, width: 320, maxHeight: 420, overflowY: 'auto', background: 'var(--panel)', border: '1px solid var(--border2)', borderRadius: 14, boxShadow: '0 12px 40px rgba(0,0,0,0.4)', zIndex: 200, padding: 8 }}>
          <div style={{ padding: '8px 12px', fontWeight: 700, fontSize: 14, color: 'var(--dim)' }}>اعلان‌ها</div>
          {items.length === 0 && <div style={{ padding: 20, textAlign: 'center', color: 'var(--faint)', fontSize: 13 }}>اعلانی نیست.</div>}
          {items.map(n => (
            <div key={n.id} onClick={() => click(n)} style={{ padding: 12, borderRadius: 10, cursor: n.link ? 'pointer' : 'default', background: n.read ? 'transparent' : 'var(--bg2)', marginBottom: 4 }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>{n.title}</div>
              <div style={{ fontSize: 12, color: 'var(--dim)', marginTop: 3, lineHeight: 1.7 }}>{n.message}</div>
              <div style={{ fontSize: 10, color: 'var(--faint)', marginTop: 4 }}>{n.created_at ? new Date(n.created_at).toLocaleString('fa-IR') : ''}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
