import { useState, useEffect, useCallback } from 'react'
import { Crown, Zap, ShieldCheck, Check, Clock, Wallet } from 'lucide-react'
import Layout from '../components/Layout'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Plan {
  id: number; name: string; plan_type: string; duration_days: number; price_toman: number;
  max_trades_per_day: number; allow_own_api: boolean; commission_tiers: { min_toman: number; pct: number }[];
  description: string; features: string[]; active: boolean
}
interface Access {
  has_access: boolean; is_superadmin: boolean; can_use_own_api: boolean; pending?: boolean;
  subscription: null | { status: string; plan_name: string; plan_type: string; end_at: string | null; days_left: number | null; max_trades_per_day: number; trades_today: number };
  commission: { applicable: boolean; rate?: number; deposit?: number; value?: number; units?: number; profit?: number; owed?: number; settled?: number; remaining?: number };
}
interface PayInfo { card_number: string; card_holder: string; account_number: string; support_contact: string }

const card: React.CSSProperties = { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }
const fmt = (n: number) => Math.round(n || 0).toLocaleString('en-US')

export default function Plans() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [access, setAccess] = useState<Access | null>(null)
  const [pay, setPay] = useState<PayInfo | null>(null)
  const [busy, setBusy] = useState(false)
  const [withdrawals, setWithdrawals] = useState<{ id: number; amount_toman: number; payout_toman: number; commission_toman: number; status: string }[]>([])

  const load = useCallback(async () => {
    try {
      const [p, a, pi, w] = await Promise.all([
        api.get('/trading/plans'),
        api.get('/trading/my-access'),
        api.get('/trading/payment-info'),
        api.get('/trading/my-withdrawals'),
      ])
      setPlans(p.data); setAccess(a.data); setPay(pi.data); setWithdrawals(w.data)
    } catch { /* ignore */ }
  }, [])

  const requestWithdraw = async () => {
    const raw = prompt('مبلغ برداشت به تومان (خالی = کل موجودی):', '')
    if (raw === null) return
    const amount = raw.trim() === '' ? 0 : Number(raw)
    if (raw.trim() !== '' && (!amount || amount <= 0)) { toast.error('مبلغ نامعتبر'); return }
    try {
      const r = await api.post('/trading/withdraw', { amount_toman: amount })
      toast.success(r.data.message || 'ثبت شد'); load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'خطا') }
  }

  useEffect(() => { load() }, [load])

  const subscribe = async (planId: number) => {
    setBusy(true)
    try {
      const r = await api.post('/trading/subscribe', { plan_id: planId })
      toast.success(r.data.message || 'درخواست ثبت شد')
      load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'خطا در ثبت درخواست')
    } finally { setBusy(false) }
  }

  const icon = (t: string) => t === 'managed' ? Crown : Zap
  const sub = access?.subscription
  const comm = access?.commission

  return (
    <Layout title="پلن‌ها" subtitle="برای استفاده از ربات معامله‌گر، یک پلن انتخاب کنید">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1100, margin: '0 auto' }}>

        {/* وضعیت اشتراک فعلی */}
        {sub && (
          <div style={{ ...card, borderColor: 'var(--green)', background: 'rgba(74,222,128,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 800, fontSize: 16, color: 'var(--green)' }}>
              <ShieldCheck size={20} /> پلن فعال: {sub.plan_name}
            </div>
            <div style={{ display: 'flex', gap: 24, marginTop: 12, flexWrap: 'wrap', fontSize: 14 }}>
              {sub.days_left !== null && <span><Clock size={14} style={{ verticalAlign: 'middle' }} /> {sub.days_left} روز باقی‌مانده</span>}
              {sub.max_trades_per_day > 0 && <span>معاملهٔ امروز: {sub.trades_today} / {sub.max_trades_per_day}</span>}
              {sub.max_trades_per_day === 0 && <span>معاملهٔ نامحدود</span>}
            </div>
          </div>
        )}

        {/* کارمزد سود (پلن مدیریت‌شده) */}
        {comm?.applicable && (
          <div style={card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontWeight: 700, fontSize: 16, marginBottom: 14 }}>
              <Wallet size={18} style={{ color: 'var(--accent)' }} /> کارمزد سود پلتفرم
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 14 }}>
              {[
                { l: 'مبلغ واریزی شما', v: fmt(comm.deposit || 0) + ' ت' },
                { l: 'ارزش فعلی', v: fmt(comm.value || 0) + ' ت', c: 'var(--accent)' },
                { l: 'سود شما', v: fmt(comm.profit || 0) + ' ت', c: (comm.profit || 0) >= 0 ? 'var(--green)' : 'var(--red)' },
                { l: 'نرخ کارمزد', v: (comm.rate || 0) + '٪' },
                { l: 'کارمزد قابل پرداخت', v: fmt(comm.remaining || 0) + ' ت', c: 'var(--amber)' },
              ].map((x, i) => (
                <div key={i} style={{ background: 'var(--bg2)', borderRadius: 12, padding: 14, textAlign: 'center' }}>
                  <div style={{ fontSize: 12, color: 'var(--dim)' }}>{x.l}</div>
                  <div style={{ fontSize: 18, fontWeight: 800, marginTop: 6, color: x.c || 'var(--text)', fontFamily: 'JetBrains Mono' }}>{x.v}</div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 12 }}>
              کارمزد فقط از سودِ مثبت محاسبه می‌شود و هنگام برداشت از سود کسر می‌گردد.
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 14, alignItems: 'center', flexWrap: 'wrap' }}>
              <button onClick={requestWithdraw} style={{ padding: '10px 20px', borderRadius: 10, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                درخواست برداشت
              </button>
              {withdrawals.filter(w => w.status === 'pending').length > 0 && (
                <span style={{ fontSize: 12, color: 'var(--amber)' }}>یک درخواست برداشت در انتظار تأیید دارید</span>
              )}
            </div>
            {withdrawals.length > 0 && (
              <div style={{ marginTop: 12, fontSize: 12, color: 'var(--dim)' }}>
                {withdrawals.slice(0, 4).map(w => (
                  <div key={w.id} style={{ display: 'flex', gap: 12, padding: '4px 0' }}>
                    <span>برداشت {w.amount_toman ? fmt(w.amount_toman) + ' ت' : 'کل موجودی'}</span>
                    <span style={{ color: w.status === 'approved' ? 'var(--green)' : w.status === 'rejected' ? 'var(--red)' : 'var(--amber)' }}>
                      {w.status === 'approved' ? `پرداخت‌شده: ${fmt(w.payout_toman)} ت` : w.status === 'rejected' ? 'ردشده' : 'در انتظار'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {access?.pending && !sub && (
          <div style={{ ...card, borderColor: 'var(--amber)', background: 'rgba(251,191,36,0.06)', color: 'var(--amber)', fontWeight: 700 }}>
            ⏳ درخواست شما ثبت شده و در انتظار تأیید ادمین است. پس از واریز وجه و تأیید، پلن فعال می‌شود.
          </div>
        )}

        {/* کارت‌های پلن */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 18 }}>
          {plans.map(p => {
            const Icon = icon(p.plan_type)
            return (
              <div key={p.id} style={{ ...card, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 12, background: 'rgba(75,224,255,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Icon size={20} style={{ color: 'var(--accent)' }} />
                  </div>
                  <div style={{ fontWeight: 800, fontSize: 17 }}>{p.name}</div>
                </div>
                <div style={{ fontSize: 22, fontWeight: 900, color: 'var(--accent)', fontFamily: 'JetBrains Mono' }}>
                  {p.price_toman > 0 ? `${fmt(p.price_toman)} ت` : (p.plan_type === 'managed' ? 'کارمزد از سود' : 'رایگان')}
                  <span style={{ fontSize: 13, color: 'var(--dim)', fontWeight: 600 }}> / {p.duration_days} روز</span>
                </div>
                {p.description && <div style={{ fontSize: 13, color: 'var(--dim)', lineHeight: 1.8 }}>{p.description}</div>}
                <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                  {(p.features || []).map((f, i) => (
                    <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Check size={15} style={{ color: 'var(--green)' }} /> {f}
                    </li>
                  ))}
                  {p.plan_type === 'managed' && (p.commission_tiers || []).map((t, i) => (
                    <li key={'c' + i} style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--amber)' }}>
                      <Check size={15} /> واریزی ≥ {fmt(t.min_toman)} ت → کارمزد {t.pct}٪ از سود
                    </li>
                  ))}
                </ul>
                <button
                  disabled={busy || (sub != null)}
                  onClick={() => subscribe(p.id)}
                  style={{
                    marginTop: 'auto', padding: '12px', borderRadius: 12, border: 'none',
                    background: sub ? 'var(--bg3)' : 'var(--accent)', color: sub ? 'var(--dim)' : '#05121a',
                    fontWeight: 800, fontSize: 14, cursor: sub ? 'default' : 'pointer', fontFamily: 'inherit',
                  }}>
                  {sub ? 'اشتراک فعال دارید' : 'انتخاب و درخواست این پلن'}
                </button>
              </div>
            )
          })}
        </div>

        {/* اطلاعات پرداخت */}
        {pay && (pay.card_number || pay.account_number) && (
          <div style={card}>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 12 }}>💳 اطلاعات پرداخت</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 14 }}>
              {pay.card_number && <div>شماره کارت: <b style={{ fontFamily: 'JetBrains Mono' }} dir="ltr">{pay.card_number}</b>{pay.card_holder && ` — به نام ${pay.card_holder}`}</div>}
              {pay.account_number && <div>شماره حساب/شبا: <b style={{ fontFamily: 'JetBrains Mono' }} dir="ltr">{pay.account_number}</b></div>}
              {pay.support_contact && <div>پس از واریز، رسید را برای ادمین بفرستید: <b dir="ltr">{pay.support_contact}</b></div>}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
