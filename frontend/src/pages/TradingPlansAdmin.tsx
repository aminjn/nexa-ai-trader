import { useState, useEffect, useCallback } from 'react'
import { Plus, Trash2, Check, X, Clock } from 'lucide-react'
import Layout from '../components/Layout'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Tier { min_toman: number; pct: number }
interface Plan {
  id: number; name: string; plan_type: string; duration_days: number; price_toman: number;
  max_trades_per_day: number; allow_own_api: boolean; commission_tiers: Tier[];
  description: string; features: string[]; active: boolean; sort: number
}
interface Sub {
  id: number; user_id: number; user_name: string; user_phone: string; plan_name: string;
  plan_type: string; status: string; deposit_toman: number; end_at: string | null; created_at: string | null;
  commission: null | { rate: number; profit: number; owed: number; settled: number; remaining: number }
}

const card: React.CSSProperties = { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }
const inputStyle: React.CSSProperties = { width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '9px 12px', color: 'var(--text)', fontSize: 13, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit' }
const label: React.CSSProperties = { fontSize: 12, color: 'var(--dim)', marginBottom: 5 }
const fmt = (n: number) => Math.round(n || 0).toLocaleString('en-US')

interface WD {
  id: number; user_name: string; user_phone: string; amount_toman: number; gross_toman: number; current_value: number | null;
  payout_toman: number; commission_toman: number; units_redeemed: number; status: string; created_at: string | null
}
interface PoolEx { id: number; name: string; user_id: number; is_pool: boolean }
interface PoolData {
  summary: { connected: boolean; exchange_id: number | null; value_toman: number; total_units: number; unit_price: number; total_deposits: number; profit: number; members: number };
  exchanges: PoolEx[]
}

export default function TradingPlansAdmin() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [subs, setSubs] = useState<Sub[]>([])
  const [poolData, setPoolData] = useState<PoolData | null>(null)
  const [withdrawals, setWithdrawals] = useState<WD[]>([])

  const load = useCallback(async () => {
    try {
      const [p, s, pl, w] = await Promise.all([
        api.get('/trading/admin/plans'),
        api.get('/trading/admin/subscriptions'),
        api.get('/trading/admin/pool'),
        api.get('/trading/admin/withdrawals'),
      ])
      setPlans(p.data); setSubs(s.data); setPoolData(pl.data); setWithdrawals(w.data)
    } catch { toast.error('خطا در بارگذاری') }
  }, [])
  useEffect(() => { load() }, [load])

  const approveWd = async (w: WD) => {
    if (!confirm(`تأیید برداشت ${w.user_name}؟ پس از تأیید باید مبلغ پرداختی را در نوبیتکس به کاربر واریز کنید.`)) return
    try { const r = await api.post(`/trading/admin/withdrawals/${w.id}/approve`); toast.success(r.data.message); load() } catch (e: any) { toast.error(e?.response?.data?.detail || 'خطا') }
  }
  const rejectWd = async (w: WD) => { try { await api.post(`/trading/admin/withdrawals/${w.id}/reject`); load() } catch { toast.error('خطا') } }

  const setPool = async (exchange_id: number) => {
    try { await api.post('/trading/admin/pool/set', { exchange_id }); toast.success('حساب استخر تنظیم شد'); load() } catch { toast.error('خطا') }
  }

  const upd = (i: number, f: keyof Plan, v: any) => setPlans(prev => prev.map((p, idx) => idx === i ? { ...p, [f]: v } : p))
  const updTier = (pi: number, ti: number, f: keyof Tier, v: number) =>
    setPlans(prev => prev.map((p, idx) => idx === pi ? { ...p, commission_tiers: p.commission_tiers.map((t, j) => j === ti ? { ...t, [f]: v } : t) } : p))
  const addTier = (pi: number) => setPlans(prev => prev.map((p, idx) => idx === pi ? { ...p, commission_tiers: [...(p.commission_tiers || []), { min_toman: 0, pct: 20 }] } : p))
  const rmTier = (pi: number, ti: number) => setPlans(prev => prev.map((p, idx) => idx === pi ? { ...p, commission_tiers: p.commission_tiers.filter((_, j) => j !== ti) } : p))

  const savePlan = async (p: Plan) => {
    const body = { ...p, features: typeof (p.features as any) === 'string' ? (p.features as any).split('\n').filter(Boolean) : p.features }
    try {
      if (p.id < 0) await api.post('/trading/admin/plans', body)
      else await api.put(`/trading/admin/plans/${p.id}`, body)
      toast.success('ذخیره شد'); load()
    } catch { toast.error('خطا در ذخیره') }
  }
  const delPlan = async (p: Plan) => {
    if (p.id < 0) { setPlans(prev => prev.filter(x => x !== p)); return }
    if (!confirm('حذف این پلن؟')) return
    try { await api.delete(`/trading/admin/plans/${p.id}`); toast.success('حذف شد'); load() } catch { toast.error('خطا') }
  }
  const addPlan = () => setPlans(prev => [...prev, {
    id: -Date.now(), name: 'پلن جدید', plan_type: 'self_api', duration_days: 30, price_toman: 0,
    max_trades_per_day: 0, allow_own_api: true, commission_tiers: [], description: '', features: [], active: true, sort: prev.length
  }])

  const activate = async (s: Sub) => {
    const dep = s.plan_type === 'managed' ? Number(prompt('مبلغ واریزی کاربر (تومان):', String(s.deposit_toman || 0)) || 0) : 0
    const d = prompt('طول پلن (روز) — خالی = پیش‌فرض پلن:', '')
    try {
      await api.post(`/trading/admin/subscriptions/${s.id}/activate`, { deposit_toman: dep, duration_days: d ? Number(d) : null })
      toast.success('فعال شد'); load()
    } catch { toast.error('خطا') }
  }
  const reject = async (s: Sub) => { try { await api.post(`/trading/admin/subscriptions/${s.id}/reject`); load() } catch { toast.error('خطا') } }
  const expire = async (s: Sub) => { if (!confirm('خاتمهٔ این اشتراک و خاموش‌کردن ربات کاربر؟')) return; try { await api.post(`/trading/admin/subscriptions/${s.id}/expire`); load() } catch { toast.error('خطا') } }
  const settle = async (s: Sub) => {
    const a = Number(prompt('مبلغ تسویه‌شدهٔ کارمزد (تومان):', String(s.commission?.remaining || 0)) || 0)
    if (a <= 0) return
    try { await api.post(`/trading/admin/subscriptions/${s.id}/settle`, { amount_toman: a }); toast.success('ثبت شد'); load() } catch { toast.error('خطا') }
  }

  const statusFa: Record<string, string> = { pending: 'در انتظار', active: 'فعال', expired: 'منقضی', rejected: 'ردشده' }
  const statusColor: Record<string, string> = { pending: 'var(--amber)', active: 'var(--green)', expired: 'var(--dim)', rejected: 'var(--red)' }

  return (
    <Layout title="پلن‌های ربات" subtitle="مدیریت پلن‌ها و اشتراک‌های معامله‌گری">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* حساب استخر مدیریت‌شده */}
        <div style={card}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>🏦 حساب استخر مدیریت‌شده (managed)</div>
          {poolData?.summary.connected ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 14, marginBottom: 16 }}>
              {[
                { l: 'ارزش کل استخر', v: fmt(poolData.summary.value_toman) + ' ت', c: 'var(--accent)' },
                { l: 'مجموع واریزی', v: fmt(poolData.summary.total_deposits) + ' ت' },
                { l: 'سود کل استخر', v: fmt(poolData.summary.profit) + ' ت', c: poolData.summary.profit >= 0 ? 'var(--green)' : 'var(--red)' },
                { l: 'قیمت هر واحد', v: poolData.summary.unit_price.toLocaleString('en-US', { maximumFractionDigits: 4 }) },
                { l: 'اعضا', v: String(poolData.summary.members) },
              ].map((x, i) => (
                <div key={i} style={{ background: 'var(--bg2)', borderRadius: 12, padding: 14, textAlign: 'center' }}>
                  <div style={{ fontSize: 12, color: 'var(--dim)' }}>{x.l}</div>
                  <div style={{ fontSize: 17, fontWeight: 800, marginTop: 6, color: x.c || 'var(--text)', fontFamily: 'JetBrains Mono' }}>{x.v}</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: 'var(--amber)', fontSize: 13, marginBottom: 12 }}>
              هنوز حساب استخری انتخاب نشده. ابتدا حساب نوبیتکسِ مشترک را در صفحهٔ «صرافی‌ها» وصل کنید، سپس این‌جا انتخابش کنید. ربات روی همین حساب معامله می‌کند.
            </div>
          )}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--dim)' }}>انتخاب حساب استخر:</span>
            {(poolData?.exchanges || []).map(e => (
              <button key={e.id} onClick={() => setPool(e.id)} style={{
                ...btn(e.is_pool ? 'var(--green)' : 'var(--border)'),
                background: e.is_pool ? 'rgba(74,222,128,0.12)' : 'transparent',
                color: e.is_pool ? 'var(--green)' : 'var(--text)',
              }}>{e.is_pool ? '✓ ' : ''}{e.name} #{e.id}</button>
            ))}
            {(poolData?.exchanges || []).length === 0 && <span style={{ fontSize: 12, color: 'var(--faint)' }}>هیچ صرافی فعالی وجود ندارد.</span>}
          </div>
        </div>

        {/* درخواست‌های برداشت */}
        {withdrawals.length > 0 && (
          <div style={card}>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>💸 درخواست‌های برداشت</div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead><tr style={{ color: 'var(--dim)', textAlign: 'right' }}>
                  {['کاربر', 'درخواست', 'ارزش قفل‌شده', 'ارزش زنده', 'پرداختی', 'کارمزد', 'وضعیت', 'عملیات'].map(c => <th key={c} style={{ padding: '8px 10px', fontWeight: 600 }}>{c}</th>)}
                </tr></thead>
                <tbody>
                  {withdrawals.map(w => (
                    <tr key={w.id} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px' }}>{w.user_name}</td>
                      <td style={{ padding: '10px', fontFamily: 'JetBrains Mono' }}>{w.amount_toman ? fmt(w.amount_toman) : 'کل موجودی'}</td>
                      <td style={{ padding: '10px', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>{w.gross_toman ? fmt(w.gross_toman) : '—'}</td>
                      <td style={{ padding: '10px', fontFamily: 'JetBrains Mono', color: 'var(--dim)' }}>{w.current_value != null ? fmt(w.current_value) : '—'}</td>
                      <td style={{ padding: '10px', fontFamily: 'JetBrains Mono', color: 'var(--green)' }}>{w.payout_toman ? fmt(w.payout_toman) : '—'}</td>
                      <td style={{ padding: '10px', fontFamily: 'JetBrains Mono', color: 'var(--amber)' }}>{w.commission_toman ? fmt(w.commission_toman) : '—'}</td>
                      <td style={{ padding: '10px', fontWeight: 700, color: w.status === 'approved' ? 'var(--green)' : w.status === 'rejected' ? 'var(--red)' : 'var(--amber)' }}>
                        {w.status === 'approved' ? 'تأییدشده' : w.status === 'rejected' ? 'ردشده' : 'در انتظار'}
                      </td>
                      <td style={{ padding: '10px' }}>
                        {w.status === 'pending' && (
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button onClick={() => approveWd(w)} title="تأیید" style={btn('var(--green)')}><Check size={15} /></button>
                            <button onClick={() => rejectWd(w)} title="رد" style={btn('var(--red)')}><X size={15} /></button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* اشتراک‌ها */}
        <div style={card}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>👥 اشتراک‌های کاربران</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ color: 'var(--dim)', textAlign: 'right' }}>
                {['کاربر', 'پلن', 'وضعیت', 'واریزی', 'کارمزد (مانده)', 'انقضا', 'عملیات'].map(c => <th key={c} style={{ padding: '8px 10px', fontWeight: 600 }}>{c}</th>)}
              </tr></thead>
              <tbody>
                {subs.map(s => (
                  <tr key={s.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '10px' }}>{s.user_name}<div style={{ fontSize: 11, color: 'var(--faint)' }} dir="ltr">{s.user_phone}</div></td>
                    <td style={{ padding: '10px' }}>{s.plan_name}<div style={{ fontSize: 11, color: 'var(--faint)' }}>{s.plan_type === 'managed' ? 'مدیریت‌شده' : 'API شخصی'}</div></td>
                    <td style={{ padding: '10px', color: statusColor[s.status], fontWeight: 700 }}>{statusFa[s.status] || s.status}</td>
                    <td style={{ padding: '10px', fontFamily: 'JetBrains Mono' }}>{fmt(s.deposit_toman)}</td>
                    <td style={{ padding: '10px', fontFamily: 'JetBrains Mono', color: 'var(--amber)' }}>{s.commission ? `${fmt(s.commission.remaining)} (${s.commission.rate}٪)` : '—'}</td>
                    <td style={{ padding: '10px', fontSize: 12 }}>{s.end_at ? new Date(s.end_at).toLocaleDateString('fa-IR') : '—'}</td>
                    <td style={{ padding: '10px' }}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {s.status !== 'active' && <button onClick={() => activate(s)} title="فعال‌سازی" style={btn('var(--green)')}><Check size={15} /></button>}
                        {s.status === 'pending' && <button onClick={() => reject(s)} title="رد" style={btn('var(--red)')}><X size={15} /></button>}
                        {s.status === 'active' && <button onClick={() => expire(s)} title="خاتمه" style={btn('var(--amber)')}><Clock size={15} /></button>}
                        {s.commission && <button onClick={() => settle(s)} title="ثبت تسویهٔ کارمزد" style={btn('var(--accent)')}>تسویه</button>}
                      </div>
                    </td>
                  </tr>
                ))}
                {subs.length === 0 && <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: 'var(--faint)' }}>اشتراکی ثبت نشده.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* ویرایش پلن‌ها */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 700 }}>📦 ویرایش پلن‌ها</div>
            <button onClick={addPlan} style={{ padding: '8px 16px', borderRadius: 10, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 6 }}><Plus size={15} /> افزودن پلن</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {plans.map((p, i) => (
              <div key={p.id} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 14, padding: 18 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
                  <div><div style={label}>نام پلن</div><input style={inputStyle} value={p.name} onChange={e => upd(i, 'name', e.target.value)} /></div>
                  <div><div style={label}>نوع</div>
                    <select style={inputStyle} value={p.plan_type} onChange={e => upd(i, 'plan_type', e.target.value)}>
                      <option value="self_api">API شخصی کاربر</option>
                      <option value="managed">مدیریت‌شده (واریز به حساب ما)</option>
                    </select></div>
                  <div><div style={label}>طول (روز)</div><input type="number" style={inputStyle} value={p.duration_days} onChange={e => upd(i, 'duration_days', Number(e.target.value))} /></div>
                  <div><div style={label}>هزینه (تومان)</div><input type="number" style={inputStyle} value={p.price_toman} onChange={e => upd(i, 'price_toman', Number(e.target.value))} /></div>
                  <div><div style={label}>سقف معامله/روز (۰=نامحدود)</div><input type="number" style={inputStyle} value={p.max_trades_per_day} onChange={e => upd(i, 'max_trades_per_day', Number(e.target.value))} /></div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 20 }}>
                    <input type="checkbox" checked={p.allow_own_api} onChange={e => upd(i, 'allow_own_api', e.target.checked)} id={'api' + i} />
                    <label htmlFor={'api' + i} style={{ fontSize: 12 }}>اجازهٔ API شخصی</label>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 20 }}>
                    <input type="checkbox" checked={p.active} onChange={e => upd(i, 'active', e.target.checked)} id={'act' + i} />
                    <label htmlFor={'act' + i} style={{ fontSize: 12 }}>فعال</label>
                  </div>
                </div>
                <div style={{ marginTop: 12 }}><div style={label}>توضیحات</div>
                  <textarea value={p.description} onChange={e => upd(i, 'description', e.target.value)} style={{ ...inputStyle, minHeight: 50, resize: 'vertical' }} /></div>
                <div style={{ marginTop: 12 }}><div style={label}>امکانات (هر خط یک مورد)</div>
                  <textarea value={(p.features || []).join('\n')} onChange={e => upd(i, 'features', e.target.value.split('\n'))} style={{ ...inputStyle, minHeight: 60, resize: 'vertical' }} /></div>

                {p.plan_type === 'managed' && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ ...label, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>پله‌های کارمزد سود (بر اساس مبلغ واریزی)</span>
                      <button onClick={() => addTier(i)} style={{ ...btn('var(--accent)'), padding: '4px 10px', fontSize: 12 }}>+ پله</button>
                    </div>
                    {(p.commission_tiers || []).map((t, ti) => (
                      <div key={ti} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                        <span style={{ fontSize: 12, color: 'var(--dim)' }}>واریزی ≥</span>
                        <input type="number" style={{ ...inputStyle, width: 150 }} value={t.min_toman} onChange={e => updTier(i, ti, 'min_toman', Number(e.target.value))} />
                        <span style={{ fontSize: 12, color: 'var(--dim)' }}>تومان → کارمزد</span>
                        <input type="number" style={{ ...inputStyle, width: 80 }} value={t.pct} onChange={e => updTier(i, ti, 'pct', Number(e.target.value))} />
                        <span style={{ fontSize: 12, color: 'var(--dim)' }}>٪</span>
                        <button onClick={() => rmTier(i, ti)} style={btn('var(--red)')}><Trash2 size={14} /></button>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
                  <button onClick={() => savePlan(p)} style={{ padding: '9px 20px', borderRadius: 10, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>ذخیره</button>
                  <button onClick={() => delPlan(p)} style={{ padding: '9px 16px', borderRadius: 10, border: '1px solid var(--red)', background: 'transparent', color: 'var(--red)', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 6 }}><Trash2 size={15} /> حذف</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Layout>
  )
}

function btn(color: string): React.CSSProperties {
  return { background: 'transparent', border: `1px solid ${color}`, color, borderRadius: 8, padding: '5px 9px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 4 }
}
