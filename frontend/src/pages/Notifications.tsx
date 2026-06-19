import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, BellOff, ShieldCheck, Wallet, ArrowUpFromLine, Info, Check, Send } from 'lucide-react'
import Layout from '../components/Layout'
import api from '../lib/api'
import toast from 'react-hot-toast'
import { ensureNotificationPermission } from '../lib/push'
import { useAuthStore } from '../stores/authStore'

interface Notif { id: number; type: string; title: string; message: string; link: string; read: boolean; created_at: string | null }

const card: React.CSSProperties = { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 16 }
const ICON: Record<string, any> = { kyc: ShieldCheck, deposit: Wallet, withdrawal: ArrowUpFromLine, system: Info }

export default function Notifications() {
  const [items, setItems] = useState<Notif[]>([])
  const [perm, setPerm] = useState<NotificationPermission>(typeof Notification !== 'undefined' ? Notification.permission : 'denied')
  const navigate = useNavigate()
  const isSuperAdmin = useAuthStore(s => s.isSuperAdmin)
  // فرم ارسال (سوپر ادمین)
  const [bTitle, setBTitle] = useState('')
  const [bMsg, setBMsg] = useState('')
  const [bTg, setBTg] = useState(true)
  const [sending, setSending] = useState(false)

  const sendBroadcast = async () => {
    if (!bTitle.trim() || !bMsg.trim()) { toast.error('عنوان و متن را وارد کنید'); return }
    setSending(true)
    try {
      const r = await api.post('/notifications/admin/broadcast', { title: bTitle, message: bMsg, send_telegram: bTg })
      toast.success(`ارسال شد: ${r.data.users} کاربر${r.data.telegram ? ` · تلگرام ${r.data.telegram}` : ''}${r.data.bale ? ` · بله ${r.data.bale}` : ''}`)
      setBTitle(''); setBMsg('')
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'خطا در ارسال') } finally { setSending(false) }
  }

  const load = useCallback(async () => {
    try { const r = await api.get('/notifications/?limit=60'); setItems(r.data.items || []) } catch { /* ignore */ }
  }, [])
  useEffect(() => { load() }, [load])

  const markAll = async () => { try { await api.post('/notifications/read-all'); load() } catch { /* */ } }
  const enablePush = async () => {
    const p = await ensureNotificationPermission()
    setPerm(p)
    if (p === 'granted') toast.success('اعلان‌های گوشی فعال شد')
    else toast.error('اجازهٔ اعلان داده نشد')
  }

  return (
    <Layout title="اعلان‌ها" subtitle="پیام‌ها و رویدادهای حساب شما">
      <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* ارسال اعلان به کاربران (سوپر ادمین) */}
        {isSuperAdmin && (
          <div style={{ ...card, padding: 20, borderColor: 'var(--accent)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 800, fontSize: 16, marginBottom: 12 }}>
              <Send size={18} style={{ color: 'var(--accent)' }} /> ارسال اعلان به همهٔ کاربران
            </div>
            <input value={bTitle} onChange={e => setBTitle(e.target.value)} placeholder="عنوان"
              style={{ width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', color: 'var(--text)', fontSize: 14, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', marginBottom: 10 }} />
            <textarea value={bMsg} onChange={e => setBMsg(e.target.value)} placeholder="متن پیام…" rows={3}
              style={{ width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', color: 'var(--text)', fontSize: 14, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', resize: 'vertical' }} />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 12, flexWrap: 'wrap', gap: 10 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--dim)' }}>
                <input type="checkbox" checked={bTg} onChange={e => setBTg(e.target.checked)} />
                ارسال به تلگرام/بلهٔ کاربران (اعلان روی گوشی)
              </label>
              <button onClick={sendBroadcast} disabled={sending} style={{ padding: '10px 22px', borderRadius: 11, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 800, fontSize: 14, cursor: 'pointer', fontFamily: 'inherit' }}>
                {sending ? 'در حال ارسال…' : 'ارسال'}
              </button>
            </div>
          </div>
        )}

        {/* فعال‌سازی اعلان روی گوشی */}
        {typeof Notification !== 'undefined' && perm !== 'granted' && (
          <div style={{ ...card, display: 'flex', alignItems: 'center', gap: 12, borderColor: 'var(--accent)' }}>
            <Bell size={22} style={{ color: 'var(--accent)' }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>دریافت اعلان روی گوشی</div>
              <div style={{ fontSize: 12, color: 'var(--dim)' }}>برای دریافت اعلانِ لحظه‌ای روی دستگاه، اجازه دهید.</div>
            </div>
            <button onClick={enablePush} style={{ padding: '9px 16px', borderRadius: 10, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>فعال‌سازی</button>
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontWeight: 800, fontSize: 16 }}>اعلان‌ها</div>
          {items.some(i => !i.read) && (
            <button onClick={markAll} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 10, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--dim)', fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
              <Check size={14} /> خواندنِ همه
            </button>
          )}
        </div>

        {items.length === 0 && (
          <div style={{ ...card, textAlign: 'center', color: 'var(--faint)', padding: 40 }}>
            <BellOff size={28} style={{ marginBottom: 8 }} /><div>اعلانی ندارید.</div>
          </div>
        )}

        {items.map(n => {
          const Icon = ICON[n.type] || Info
          return (
            <div key={n.id} onClick={() => n.link && navigate(n.link)} style={{ ...card, display: 'flex', gap: 12, cursor: n.link ? 'pointer' : 'default', borderColor: n.read ? 'var(--border)' : 'var(--accent)', background: n.read ? 'var(--panel)' : 'rgba(75,224,255,0.05)' }}>
              <div style={{ width: 38, height: 38, borderRadius: 10, background: 'var(--bg2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <Icon size={18} style={{ color: 'var(--accent)' }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{n.title}</div>
                <div style={{ fontSize: 13, color: 'var(--dim)', marginTop: 3, lineHeight: 1.8 }}>{n.message}</div>
                <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 5 }}>{n.created_at ? new Date(n.created_at).toLocaleString('fa-IR') : ''}</div>
              </div>
              {!n.read && <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0, marginTop: 6 }} />}
            </div>
          )
        })}
      </div>
    </Layout>
  )
}
