import { useState, useEffect, useCallback } from 'react'
import { Radio, Send, Check, X, RefreshCw, Crown, Zap, Gift } from 'lucide-react'
import Layout from '../components/Layout'
import { useAuthStore } from '../stores/authStore'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Plan {
  id: number; key: string; name: string; level: number; price_toman: number;
  duration_days: number; max_coins: number; delay_minutes: number;
  include_analysis: boolean; channels: string[]; description: string; active: boolean
}
interface Signal {
  id: number; coin: string; side: string; confidence: number;
  entry_price: number; target_price: number; stop_price: number;
  tech_conclusion: string; fund_conclusion: string; analysis: string; created_at: string
}
interface SubInfo {
  plan: Plan; status: string; end_at: string | null; pending: Plan | null;
  telegram_chat_id: string; bale_chat_id: string
}
interface AdminSub {
  id: number; user: string; user_id: number; plan: string; status: string;
  payment_method: string; amount_toman: number; created_at: string; end_at: string | null
}

const card: React.CSSProperties = { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }
const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10,
  padding: '10px 14px', color: 'var(--text)', fontSize: 14, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit',
}
const label: React.CSSProperties = { color: 'var(--faint)', fontSize: 12, marginBottom: 6, fontWeight: 600 }
const fmt = (n: number) => Math.round(n || 0).toLocaleString('fa-IR')
const planIcon = (lvl: number) => lvl >= 2 ? <Crown size={18} /> : lvl === 1 ? <Zap size={18} /> : <Gift size={18} />

export default function Signals() {
  const isSuperAdmin = useAuthStore(s => s.isSuperAdmin)
  const [plans, setPlans] = useState<Plan[]>([])
  const [sub, setSub] = useState<SubInfo | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [tg, setTg] = useState('')
  const [bale, setBale] = useState('')

  // admin
  const [adminSettings, setAdminSettings] = useState<any>(null)
  const [adminSubs, setAdminSubs] = useState<AdminSub[]>([])
  const [generating, setGenerating] = useState(false)

  const load = useCallback(async () => {
    try {
      const [p, s, f] = await Promise.all([
        api.get<Plan[]>('/signals/plans'),
        api.get<SubInfo>('/signals/subscription'),
        api.get<{ signals: Signal[] }>('/signals/feed'),
      ])
      setPlans(p.data || [])
      setSub(s.data)
      setTg(s.data?.telegram_chat_id || '')
      setBale(s.data?.bale_chat_id || '')
      setSignals(f.data?.signals || [])
    } catch { /* ignore */ }
  }, [])

  const loadAdmin = useCallback(async () => {
    if (!isSuperAdmin) return
    try {
      const [st, su] = await Promise.all([
        api.get('/signals/admin/settings'),
        api.get<AdminSub[]>('/signals/admin/subscriptions'),
      ])
      setAdminSettings(st.data)
      setAdminSubs(su.data || [])
    } catch { /* ignore */ }
  }, [isSuperAdmin])

  useEffect(() => { load(); loadAdmin() }, [load, loadAdmin])
  useEffect(() => { const id = setInterval(load, 20000); return () => clearInterval(id) }, [load])

  const saveConnect = async () => {
    try {
      await api.post('/signals/connect', { telegram_chat_id: tg, bale_chat_id: bale })
      toast.success('شناسه‌ها ذخیره شد')
    } catch { toast.error('خطا در ذخیره') }
  }

  const subscribe = async (plan: Plan) => {
    try {
      if (plan.price_toman <= 0) {
        await api.post('/signals/subscribe', { plan_id: plan.id })
        toast.success('پلن رایگان فعال شد'); load(); return
      }
      // پولی: تلاش برای درگاه آنلاین، در صورت نبود درگاه → درخواست دستی
      try {
        const r = await api.post<{ pay_url: string }>('/signals/pay/request', { plan_id: plan.id })
        if (r.data?.pay_url) { window.location.href = r.data.pay_url; return }
      } catch {
        await api.post('/signals/subscribe', { plan_id: plan.id })
        toast.success('درخواست ثبت شد — پس از پرداخت کارت‌به‌کارت و تأیید ادمین فعال می‌شود')
        load(); return
      }
    } catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
  }

  const saveAdminSettings = async () => {
    try { await api.post('/signals/admin/settings', adminSettings); toast.success('تنظیمات ذخیره شد') }
    catch { toast.error('خطا') }
  }
  const generateNow = async () => {
    setGenerating(true)
    try { const r = await api.post('/signals/admin/generate-now'); toast.success(r.data.message); load() }
    catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
    finally { setGenerating(false) }
  }
  const activate = async (id: number) => { try { await api.post(`/signals/admin/subscriptions/${id}/activate`); toast.success('فعال شد'); loadAdmin() } catch { toast.error('خطا') } }
  const reject = async (id: number) => { try { await api.post(`/signals/admin/subscriptions/${id}/reject`); loadAdmin() } catch { toast.error('خطا') } }

  const sideColor = (s: string) => s === 'BUY' ? 'var(--green)' : s === 'SELL' ? '#ef4444' : 'var(--dim)'
  const sideFa = (s: string) => s === 'BUY' ? '🟢 خرید' : s === 'SELL' ? '🔴 فروش' : '⏳ صبر'

  return (
    <Layout title="سیگنال‌ها و اشتراک" subtitle="دریافت سیگنال بر اساس پلن شما — در پنل، تلگرام و بله">
      <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>

        {/* پلن فعلی + اتصال پیام‌رسان */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {planIcon(sub?.plan.level ?? 0)}
              <div>
                <div style={{ fontWeight: 700, fontSize: 16 }}>پلن فعلی: {sub?.plan.name || 'رایگان'}</div>
                <div style={{ fontSize: 12, color: 'var(--dim)' }}>
                  وضعیت: {sub?.status === 'active' ? 'فعال' : 'رایگان'}
                  {sub?.end_at ? ` · تا ${new Date(sub.end_at).toLocaleDateString('fa-IR')}` : ''}
                  {sub?.pending ? ` · در انتظار تأیید: ${sub.pending.name}` : ''}
                </div>
              </div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 18 }}>
            <div>
              <div style={label}>شناسه عددی تلگرام (chat id)</div>
              <input style={inputStyle} value={tg} onChange={e => setTg(e.target.value)} placeholder="مثلاً 123456789" dir="ltr" />
            </div>
            <div>
              <div style={label}>شناسه عددی بله (chat id)</div>
              <input style={inputStyle} value={bale} onChange={e => setBale(e.target.value)} placeholder="شناسه بله" dir="ltr" />
            </div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 8 }}>
            برای دریافت سیگنال در تلگرام، ابتدا ربات را استارت کن و شناسه عددی‌ات را از <span dir="ltr">@userinfobot</span> بگیر.
          </div>
          <button onClick={saveConnect} style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 7, padding: '10px 20px', borderRadius: 11, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
            <Send size={15} /> ذخیره شناسه‌ها
          </button>
        </div>

        {/* پلن‌ها */}
        <div style={card}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>پلن‌های اشتراک</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 14 }}>
            {plans.map(p => (
              <div key={p.id} style={{ padding: 18, borderRadius: 14, background: 'var(--bg2)', border: `1px solid ${sub?.plan.id === p.id ? 'var(--accent)' : 'var(--border)'}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 15 }}>{planIcon(p.level)} {p.name}</div>
                <div style={{ fontSize: 20, fontWeight: 800, margin: '10px 0', color: 'var(--accent)' }}>
                  {p.price_toman > 0 ? `${fmt(p.price_toman)} تومان` : 'رایگان'}
                  {p.price_toman > 0 && <span style={{ fontSize: 11, color: 'var(--faint)', fontWeight: 400 }}> / {p.duration_days} روز</span>}
                </div>
                <div style={{ fontSize: 12, color: 'var(--dim)', lineHeight: 1.7, minHeight: 54 }}>{p.description}</div>
                <ul style={{ fontSize: 11, color: 'var(--faint)', paddingInlineStart: 16, margin: '8px 0', lineHeight: 1.9 }}>
                  <li>{p.delay_minutes > 0 ? `با ${p.delay_minutes} دقیقه تأخیر` : 'سیگنال آنی'}</li>
                  <li>{p.include_analysis ? 'شامل تحلیل کامل' : 'بدون تحلیل کامل'}</li>
                  <li>کانال‌ها: {(p.channels || []).map(c => c === 'telegram' ? 'تلگرام' : c === 'bale' ? 'بله' : 'پنل').join('، ')}</li>
                </ul>
                {sub?.plan.id === p.id ? (
                  <div style={{ textAlign: 'center', fontSize: 12, color: 'var(--green)', fontWeight: 700, padding: 8 }}>✓ پلن فعلی شما</div>
                ) : (
                  <button onClick={() => subscribe(p)} style={{ width: '100%', padding: '10px', borderRadius: 10, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                    {p.price_toman > 0 ? 'خرید / ارتقا' : 'فعال‌سازی رایگان'}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* فید سیگنال */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16, fontWeight: 700, marginBottom: 16 }}>
            <Radio size={18} style={{ color: 'var(--accent)' }} /> آخرین سیگنال‌ها
          </div>
          {signals.length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--faint)', padding: 30, fontSize: 14 }}>هنوز سیگنالی برای پلن شما منتشر نشده.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {signals.map(s => (
                <div key={s.id} style={{ padding: 16, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontWeight: 800, fontFamily: "'JetBrains Mono'" }}>{s.coin}</span>
                      <span style={{ fontWeight: 700, color: sideColor(s.side) }}>{sideFa(s.side)}</span>
                      <span style={{ fontSize: 12, color: 'var(--dim)' }}>اطمینان {Math.round(s.confidence * 100)}٪</span>
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--faint)' }}>{new Date(s.created_at).toLocaleString('fa-IR')}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 18, marginTop: 8, fontSize: 13, flexWrap: 'wrap' }}>
                    <span>قیمت: <b>{fmt(s.entry_price)}</b> ت</span>
                    {s.side === 'BUY' && <span style={{ color: 'var(--green)' }}>هدف: {fmt(s.target_price)} ت</span>}
                    {s.side === 'BUY' && <span style={{ color: '#ef4444' }}>حد ضرر: {fmt(s.stop_price)} ت</span>}
                    <span style={{ color: 'var(--dim)' }}>تکنیکال: {s.tech_conclusion} | فاندامنتال: {s.fund_conclusion}</span>
                  </div>
                  {s.analysis && <div style={{ marginTop: 10, padding: 10, background: 'var(--bg3)', borderRadius: 8, fontSize: 12, color: 'var(--dim)', whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{s.analysis}</div>}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── بخش ادمین ── */}
        {isSuperAdmin && adminSettings && (
          <>
            <div style={card}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
                <div style={{ fontSize: 16, fontWeight: 700 }}>⚙️ تنظیمات فروش سیگنال (ادمین)</div>
                <button onClick={generateNow} disabled={generating} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 11, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--text)', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                  <RefreshCw size={14} style={{ animation: generating ? 'spin 1s linear infinite' : 'none' }} /> تولید و ارسال فوری سیگنال
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div><div style={label}>توکن ربات تلگرام</div>
                  <input style={inputStyle} value={adminSettings.telegram_bot_token} onChange={e => setAdminSettings({ ...adminSettings, telegram_bot_token: e.target.value })} dir="ltr" /></div>
                <div><div style={label}>توکن ربات بله</div>
                  <input style={inputStyle} value={adminSettings.bale_bot_token} onChange={e => setAdminSettings({ ...adminSettings, bale_bot_token: e.target.value })} dir="ltr" /></div>
                <div><div style={label}>مرچنت‌آیدی زرین‌پال (اختیاری)</div>
                  <input style={inputStyle} value={adminSettings.zarinpal_merchant_id} onChange={e => setAdminSettings({ ...adminSettings, zarinpal_merchant_id: e.target.value })} dir="ltr" /></div>
                <div><div style={label}>ارزهای تولید سیگنال (با کاما)</div>
                  <input style={inputStyle} value={adminSettings.signal_coins} onChange={e => setAdminSettings({ ...adminSettings, signal_coins: e.target.value })} dir="ltr" placeholder="BTC,ETH,XRP" /></div>
                <div><div style={label}>هر چند دقیقه تولید شود</div>
                  <input type="number" min={5} style={inputStyle} value={adminSettings.signal_interval_minutes} onChange={e => setAdminSettings({ ...adminSettings, signal_interval_minutes: Number(e.target.value) })} /></div>
              </div>
              <button onClick={saveAdminSettings} style={{ marginTop: 14, padding: '10px 22px', borderRadius: 11, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>ذخیره تنظیمات</button>
            </div>

            <div style={card}>
              <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>👥 اشتراک‌ها</div>
              {adminSubs.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--faint)', padding: 20, fontSize: 14 }}>اشتراکی ثبت نشده.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {adminSubs.map(s => (
                    <div key={s.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: 12, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, flexWrap: 'wrap' }}>
                      <div style={{ fontSize: 13 }}>
                        <b>{s.user}</b> · {s.plan} · {fmt(s.amount_toman)} ت · {s.payment_method === 'online' ? 'آنلاین' : 'دستی'}
                        <span style={{ marginInlineStart: 8, fontSize: 11, color: s.status === 'active' ? 'var(--green)' : s.status === 'pending' ? 'var(--amber)' : 'var(--dim)' }}>
                          [{s.status === 'active' ? 'فعال' : s.status === 'pending' ? 'در انتظار' : s.status}]
                        </span>
                      </div>
                      {s.status === 'pending' && (
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button onClick={() => activate(s.id)} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '7px 14px', borderRadius: 9, border: 'none', background: 'var(--green)', color: '#05121a', fontWeight: 700, fontSize: 12, cursor: 'pointer' }}><Check size={13} /> فعال‌سازی</button>
                          <button onClick={() => reject(s.id)} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '7px 14px', borderRadius: 9, border: '1px solid rgba(239,68,68,0.4)', background: 'transparent', color: '#ef4444', fontWeight: 600, fontSize: 12, cursor: 'pointer' }}><X size={13} /> رد</button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
