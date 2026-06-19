import { useState, useEffect, useCallback } from 'react'
import { Radio, Check, X, RefreshCw, Crown, Zap, Gift, Megaphone } from 'lucide-react'
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
  const [link, setLink] = useState<any>(null)
  const [publishing, setPublishing] = useState(false)

  // admin
  const [adminSettings, setAdminSettings] = useState<any>(null)
  const [adminSubs, setAdminSubs] = useState<AdminSub[]>([])
  const [generating, setGenerating] = useState(false)
  const [testResult, setTestResult] = useState<any>(null)
  const [adminPlans, setAdminPlans] = useState<Plan[]>([])
  const [availableCoins, setAvailableCoins] = useState<string[]>([])

  const load = useCallback(async () => {
    try {
      const [p, s, f, l] = await Promise.all([
        api.get<Plan[]>('/signals/plans'),
        api.get<SubInfo>('/signals/subscription'),
        api.get<{ signals: Signal[] }>('/signals/feed'),
        api.get('/signals/link-code'),
      ])
      setPlans(p.data || [])
      setSub(s.data)
      setSignals(f.data?.signals || [])
      setLink(l.data)
    } catch { /* ignore */ }
  }, [])

  const loadAdmin = useCallback(async () => {
    if (!isSuperAdmin) return
    try {
      const [st, su, pl, co] = await Promise.all([
        api.get('/signals/admin/settings'),
        api.get<AdminSub[]>('/signals/admin/subscriptions'),
        api.get<Plan[]>('/signals/admin/plans'),
        api.get<{ coins: string[] }>('/signals/admin/available-coins'),
      ])
      setAdminSettings(st.data)
      setAdminSubs(su.data || [])
      setAdminPlans(pl.data || [])
      setAvailableCoins(co.data?.coins || [])
    } catch { /* ignore */ }
  }, [isSuperAdmin])

  const selectedCoins = () => (adminSettings?.signal_coins || '').split(',').map((c: string) => c.trim().toUpperCase()).filter(Boolean)
  const toggleSignalCoin = (coin: string) => {
    const cur = selectedCoins()
    const next = cur.includes(coin) ? cur.filter((c: string) => c !== coin) : [...cur, coin]
    setAdminSettings({ ...adminSettings, signal_coins: next.join(',') })
  }
  const selectAllCoins = () => setAdminSettings({ ...adminSettings, signal_coins: availableCoins.join(',') })
  const clearCoins = () => setAdminSettings({ ...adminSettings, signal_coins: '' })

  const setPlanField = (idx: number, field: string, value: any) => {
    setAdminPlans(prev => prev.map((p, i) => i === idx ? { ...p, [field]: value } : p))
  }
  const toggleChannel = (idx: number, ch: string) => {
    setAdminPlans(prev => prev.map((p, i) => {
      if (i !== idx) return p
      const chs = p.channels || []
      return { ...p, channels: chs.includes(ch) ? chs.filter(c => c !== ch) : [...chs, ch] }
    }))
  }
  const savePlan = async (p: Plan) => {
    try {
      const body = { key: p.key, name: p.name, level: p.level, price_toman: p.price_toman, duration_days: p.duration_days,
        max_coins: p.max_coins, delay_minutes: p.delay_minutes, include_analysis: p.include_analysis,
        channels: p.channels || [], description: p.description || '', active: p.active, sort: (p as any).sort || p.level }
      if (p.id) await api.put(`/signals/admin/plans/${p.id}`, body)
      else await api.post('/signals/admin/plans', body)
      toast.success('پلن ذخیره شد'); loadAdmin(); load()
    } catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
  }
  const deletePlan = async (p: Plan) => {
    if (!p.id) { setAdminPlans(prev => prev.filter(x => x !== p)); return }
    if (!window.confirm(`پلن «${p.name}» حذف شود؟`)) return
    try { await api.delete(`/signals/admin/plans/${p.id}`); toast.success('حذف شد'); loadAdmin(); load() }
    catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
  }
  const addPlan = () => {
    setAdminPlans(prev => [...prev, { id: 0, key: `plan${Date.now()}`, name: 'پلن جدید', level: 1, price_toman: 100000,
      duration_days: 30, max_coins: 5, delay_minutes: 0, include_analysis: false, channels: ['telegram','bale','inapp'],
      description: '', active: true } as any])
  }

  useEffect(() => { load(); loadAdmin() }, [load, loadAdmin])
  useEffect(() => { const id = setInterval(load, 20000); return () => clearInterval(id) }, [load])

  const copyCode = () => {
    if (link?.code) { navigator.clipboard?.writeText(link.code); toast.success('کد کپی شد') }
  }
  const publishNow = async () => {
    setPublishing(true)
    try { const r = await api.post('/signals/admin/publish-now'); toast.success(r.data.message) }
    catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
    finally { setPublishing(false) }
  }
  const publishAd = async () => {
    try { const r = await api.post('/signals/admin/publish-ad'); toast.success(r.data.message) }
    catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
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
  const testChannel = async () => {
    setTestResult({ loading: true })
    try { const r = await api.post('/signals/admin/test-channel'); setTestResult(r.data) }
    catch (e: any) { setTestResult({ error: e.response?.data?.detail || 'خطا' }) }
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
          <div style={{ marginTop: 18, padding: 16, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>🔗 اتصال خودکار پیام‌رسان</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
              <span style={{ fontSize: 13 }}>تلگرام: {link?.telegram_connected ? <b style={{ color: 'var(--green)' }}>✓ متصل</b> : <span style={{ color: 'var(--dim)' }}>متصل نیست</span>}</span>
              <span style={{ fontSize: 13 }}>بله: {link?.bale_connected ? <b style={{ color: 'var(--green)' }}>✓ متصل</b> : <span style={{ color: 'var(--dim)' }}>متصل نیست</span>}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, color: 'var(--dim)' }}>در ربات این دستور را بفرست:</span>
              <code onClick={copyCode} title="کپی" style={{ cursor: 'pointer', background: 'var(--bg3)', border: '1px solid var(--accent)', borderRadius: 8, padding: '6px 12px', fontFamily: "'JetBrains Mono'", color: 'var(--accent)', fontWeight: 700 }} dir="ltr">/start {link?.code || '...'}</code>
              <button onClick={load} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 9, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--text)', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}><RefreshCw size={13} /> بررسی اتصال</button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 10, lineHeight: 1.8 }}>
              {link?.telegram_bot ? <>ربات تلگرام: <b dir="ltr">{link.telegram_bot}</b> — </> : null}
              {link?.bale_bot ? <>ربات بله: <b dir="ltr">{link.bale_bot}</b> — </> : null}
              کافیست ربات را باز کنی و دستور بالا را ارسال کنی؛ حسابت خودکار وصل می‌شود.
            </div>
          </div>
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
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button onClick={generateNow} disabled={generating} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 11, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--text)', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                    <RefreshCw size={14} style={{ animation: generating ? 'spin 1s linear infinite' : 'none' }} /> تولید و ارسال فوری سیگنال
                  </button>
                  <button onClick={publishNow} disabled={publishing} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 11, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--text)', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                    <Megaphone size={14} style={{ animation: publishing ? 'spin 1s linear infinite' : 'none' }} /> انتشار فوری محتوا در کانال
                  </button>
                  <button onClick={publishAd} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 11, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--text)', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                    📣 انتشار فوری تبلیغ
                  </button>
                  <button onClick={testChannel} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 11, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                    🧪 تست ارسال به کانال
                  </button>
                </div>
              </div>
              {testResult && (
                <div style={{ marginBottom: 14, padding: 12, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, fontSize: 12, lineHeight: 1.9 }}>
                  {testResult.loading ? 'در حال تست...' : testResult.error ? <span style={{ color: '#ef4444' }}>{testResult.error}</span> : (
                    <>
                      <div>تلگرام: {testResult.telegram?.ok ? <b style={{ color: 'var(--green)' }}>✓ موفق</b> : <span style={{ color: '#ef4444' }}>✗ ناموفق</span>} <span style={{ color: 'var(--faint)', direction: 'ltr', display: 'inline-block' }}>{testResult.telegram?.detail}</span></div>
                      <div>بله: {testResult.bale?.ok ? <b style={{ color: 'var(--green)' }}>✓ موفق</b> : <span style={{ color: '#ef4444' }}>✗ ناموفق</span>} <span style={{ color: 'var(--faint)', direction: 'ltr', display: 'inline-block' }}>{testResult.bale?.detail}</span></div>
                    </>
                  )}
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div><div style={label}>توکن ربات تلگرام</div>
                  <input style={inputStyle} value={adminSettings.telegram_bot_token} onChange={e => setAdminSettings({ ...adminSettings, telegram_bot_token: e.target.value })} dir="ltr" /></div>
                <div><div style={label}>توکن ربات بله</div>
                  <input style={inputStyle} value={adminSettings.bale_bot_token} onChange={e => setAdminSettings({ ...adminSettings, bale_bot_token: e.target.value })} dir="ltr" /></div>
                <div><div style={label}>یوزرنیم ربات تلگرام (برای راهنما)</div>
                  <input style={inputStyle} value={adminSettings.telegram_bot_username} onChange={e => setAdminSettings({ ...adminSettings, telegram_bot_username: e.target.value })} dir="ltr" placeholder="@MyBot" /></div>
                <div><div style={label}>یوزرنیم ربات بله</div>
                  <input style={inputStyle} value={adminSettings.bale_bot_username} onChange={e => setAdminSettings({ ...adminSettings, bale_bot_username: e.target.value })} dir="ltr" /></div>
                <div><div style={label}>آی‌دی کانال تلگرام (انتشار محتوا)</div>
                  <input style={inputStyle} value={adminSettings.telegram_channel_id} onChange={e => setAdminSettings({ ...adminSettings, telegram_channel_id: e.target.value })} dir="ltr" placeholder="@MyChannel" /></div>
                <div><div style={label}>آی‌دی کانال بله</div>
                  <input style={inputStyle} value={adminSettings.bale_channel_id} onChange={e => setAdminSettings({ ...adminSettings, bale_channel_id: e.target.value })} dir="ltr" /></div>
                <div><div style={label}>مرچنت‌آیدی زرین‌پال (اختیاری)</div>
                  <input style={inputStyle} value={adminSettings.zarinpal_merchant_id} onChange={e => setAdminSettings({ ...adminSettings, zarinpal_merchant_id: e.target.value })} dir="ltr" /></div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                    <div style={label}>ارزهای تولید سیگنال ({selectedCoins().length} انتخاب‌شده)</div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button type="button" onClick={selectAllCoins} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 8, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', cursor: 'pointer', fontFamily: 'inherit' }}>انتخاب همه</button>
                      <button type="button" onClick={clearCoins} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 8, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--dim)', cursor: 'pointer', fontFamily: 'inherit' }}>پاک کردن</button>
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8, maxHeight: 150, overflowY: 'auto', padding: 8, background: 'var(--bg2)', borderRadius: 10, border: '1px solid var(--border)' }}>
                    {availableCoins.map(coin => {
                      const on = selectedCoins().includes(coin)
                      return (
                        <span key={coin} onClick={() => toggleSignalCoin(coin)} style={{ cursor: 'pointer', userSelect: 'none', padding: '5px 10px', borderRadius: 999, fontSize: 12, fontFamily: "'JetBrains Mono'", border: `1px solid ${on ? 'var(--accent)' : 'var(--border)'}`, background: on ? 'color-mix(in srgb, var(--accent) 18%, transparent)' : 'transparent', color: on ? 'var(--accent)' : 'var(--dim)' }}>
                          {on ? '✓ ' : ''}{coin}
                        </span>
                      )
                    })}
                  </div>
                </div>
                <div><div style={label}>سیگنال هر چند دقیقه (تلگرام + بله)</div>
                  <input type="number" min={1} style={inputStyle} value={adminSettings.signal_interval_minutes} onChange={e => setAdminSettings({ ...adminSettings, signal_interval_minutes: Number(e.target.value) })} /></div>
                <div><div style={label}>محتوای تحلیلی هر چند ساعت (تلگرام + بله)</div>
                  <input type="number" min={1} style={inputStyle} value={adminSettings.content_interval_hours} onChange={e => setAdminSettings({ ...adminSettings, content_interval_hours: Number(e.target.value) })} /></div>
                <div><div style={label}>تبلیغ هوش مصنوعی هر چند ساعت</div>
                  <input type="number" min={1} style={inputStyle} value={adminSettings.ad_interval_hours} onChange={e => setAdminSettings({ ...adminSettings, ad_interval_hours: Number(e.target.value) })} /></div>
                <div><div style={label}>شماره کارت (پرداخت کارت‌به‌کارت)</div>
                  <input style={inputStyle} value={adminSettings.card_number} onChange={e => setAdminSettings({ ...adminSettings, card_number: e.target.value })} dir="ltr" placeholder="6037-XXXX-XXXX-XXXX" /></div>
                <div><div style={label}>نام صاحب کارت</div>
                  <input style={inputStyle} value={adminSettings.card_holder} onChange={e => setAdminSettings({ ...adminSettings, card_holder: e.target.value })} placeholder="نام و نام خانوادگی" /></div>
                <div><div style={label}>شماره حساب / شبا</div>
                  <input style={inputStyle} value={adminSettings.account_number} onChange={e => setAdminSettings({ ...adminSettings, account_number: e.target.value })} dir="ltr" placeholder="IR000000000000000000000000" /></div>
                <div><div style={label}>آی‌دی ادمین پشتیبانی (ارسال رسید)</div>
                  <input style={inputStyle} value={adminSettings.support_contact} onChange={e => setAdminSettings({ ...adminSettings, support_contact: e.target.value })} dir="ltr" placeholder="@NexaSupport" /></div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingTop: 22 }}>
                  <input type="checkbox" id="aisup" checked={!!adminSettings.ai_support_enabled} onChange={e => setAdminSettings({ ...adminSettings, ai_support_enabled: e.target.checked })} />
                  <label htmlFor="aisup" style={{ fontSize: 13, cursor: 'pointer' }}>پاسخ‌گویی هوش مصنوعی در ربات فعال باشد</label>
                </div>
              </div>
              <button onClick={saveAdminSettings} style={{ marginTop: 14, padding: '10px 22px', borderRadius: 11, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>ذخیره تنظیمات</button>
            </div>

            {/* ویرایش پلن‌ها */}
            <div style={card}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div style={{ fontSize: 16, fontWeight: 700 }}>📦 ویرایش پلن‌ها</div>
                <button onClick={addPlan} style={{ padding: '8px 16px', borderRadius: 10, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>+ افزودن پلن</button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {adminPlans.map((p, i) => (
                  <div key={p.id || `new${i}`} style={{ padding: 16, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
                      <div><div style={label}>نام پلن</div><input style={inputStyle} value={p.name} onChange={e => setPlanField(i, 'name', e.target.value)} /></div>
                      <div><div style={label}>قیمت (تومان)</div><input type="number" style={inputStyle} value={p.price_toman} onChange={e => setPlanField(i, 'price_toman', Number(e.target.value))} /></div>
                      <div><div style={label}>مدت (روز)</div><input type="number" style={inputStyle} value={p.duration_days} onChange={e => setPlanField(i, 'duration_days', Number(e.target.value))} /></div>
                      <div><div style={label}>سطح (۰=رایگان،۱،۲)</div><input type="number" style={inputStyle} value={p.level} onChange={e => setPlanField(i, 'level', Number(e.target.value))} /></div>
                      <div><div style={label}>تأخیر (دقیقه)</div><input type="number" style={inputStyle} value={p.delay_minutes} onChange={e => setPlanField(i, 'delay_minutes', Number(e.target.value))} /></div>
                      <div><div style={label}>حداکثر ارز</div><input type="number" style={inputStyle} value={p.max_coins} onChange={e => setPlanField(i, 'max_coins', Number(e.target.value))} /></div>
                    </div>
                    <div style={{ marginTop: 10 }}><div style={label}>توضیحات</div>
                      <input style={inputStyle} value={p.description} onChange={e => setPlanField(i, 'description', e.target.value)} /></div>
                    <div style={{ display: 'flex', gap: 16, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                        <input type="checkbox" checked={p.include_analysis} onChange={e => setPlanField(i, 'include_analysis', e.target.checked)} /> شامل تحلیل کامل
                      </label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                        <input type="checkbox" checked={p.active} onChange={e => setPlanField(i, 'active', e.target.checked)} /> فعال
                      </label>
                      <span style={{ fontSize: 12, color: 'var(--dim)' }}>کانال‌ها:</span>
                      {['telegram', 'bale', 'inapp'].map(ch => (
                        <label key={ch} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, cursor: 'pointer' }}>
                          <input type="checkbox" checked={(p.channels || []).includes(ch)} onChange={() => toggleChannel(i, ch)} />
                          {ch === 'telegram' ? 'تلگرام' : ch === 'bale' ? 'بله' : 'پنل'}
                        </label>
                      ))}
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                      <button onClick={() => savePlan(p)} style={{ padding: '8px 18px', borderRadius: 9, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>ذخیره</button>
                      <button onClick={() => deletePlan(p)} style={{ padding: '8px 14px', borderRadius: 9, border: '1px solid rgba(239,68,68,0.4)', background: 'transparent', color: '#ef4444', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>حذف</button>
                    </div>
                  </div>
                ))}
              </div>
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
