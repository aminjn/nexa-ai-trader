import { useState, useEffect, useCallback } from 'react'
import { Wallet as WalletIcon, ArrowDownToLine, ArrowUpFromLine, Upload } from 'lucide-react'
import Layout from '../components/Layout'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Hist { id: number; kind: string; amount_toman: number; payout_toman?: number; commission_toman?: number; purpose?: string; status: string; reference?: string; note?: string; created_at: string | null }
interface WalletData {
  type: string; balance_toman: number; invested_toman: number; profit_toman: number; kyc_status: string;
  payment_info: { card_number: string; card_holder: string; account_number: string; support_contact: string };
  history: Hist[]
}

const card: React.CSSProperties = { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }
const input: React.CSSProperties = { width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', color: 'var(--text)', fontSize: 14, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit' }
const fmt = (n: number) => Math.round(n || 0).toLocaleString('en-US')
const ST: Record<string, { t: string; c: string }> = {
  pending: { t: 'در انتظار', c: 'var(--amber)' }, approved: { t: 'تأییدشده', c: 'var(--green)' },
  rejected: { t: 'ردشده', c: 'var(--red)' }, expired: { t: 'انجام‌شده', c: 'var(--dim)' },
}

function fileToDataUri(file: File): Promise<string> {
  return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result as string); r.onerror = rej; r.readAsDataURL(file) })
}

export default function Wallet() {
  const [w, setW] = useState<WalletData | null>(null)
  const [amount, setAmount] = useState('')
  const [reference, setReference] = useState('')
  const [receipt, setReceipt] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try { const r = await api.get<WalletData>('/wallet/'); setW(r.data) } catch { /* ignore */ }
  }, [])
  useEffect(() => { load() }, [load])

  const managed = w?.type === 'managed'

  const deposit = async () => {
    const amt = Number(amount)
    if (!amt || amt <= 0) { toast.error('مبلغ را وارد کنید'); return }
    setBusy(true)
    try {
      const r = await api.post('/wallet/deposit', { amount_toman: amt, reference, receipt_image: receipt, purpose: managed ? 'invest' : 'wallet' })
      toast.success(r.data.message || 'ثبت شد'); setAmount(''); setReference(''); setReceipt(''); load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'خطا') } finally { setBusy(false) }
  }

  const withdraw = async () => {
    const raw = prompt(managed ? 'مبلغ برداشت از سرمایه (خالی = کل):' : 'مبلغ برداشت از کیف پول (تومان):', '')
    if (raw === null) return
    const amt = raw.trim() === '' ? 0 : Number(raw)
    try {
      if (managed) {
        const r = await api.post('/trading/withdraw', { amount_toman: amt })
        toast.success(r.data.message || 'ثبت شد')
      } else {
        if (!amt || amt <= 0) { toast.error('مبلغ نامعتبر'); return }
        const r = await api.post('/wallet/withdraw', { amount_toman: amt })
        toast.success(r.data.message || 'ثبت شد')
      }
      load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'خطا') }
  }

  const pickReceipt = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (f) setReceipt(await fileToDataUri(f))
  }

  const pi = w?.payment_info
  return (
    <Layout title="کیف پول" subtitle="واریز، برداشت و تاریخچهٔ تراکنش‌ها">
      <div style={{ maxWidth: 900, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* موجودی */}
        <div style={{ ...card, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ width: 56, height: 56, borderRadius: 16, background: 'rgba(75,224,255,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <WalletIcon size={28} style={{ color: 'var(--accent)' }} />
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--dim)' }}>{managed ? 'ارزش سرمایهٔ شما' : 'موجودی کیف پول'}</div>
            <div style={{ fontSize: 28, fontWeight: 900, fontFamily: 'JetBrains Mono', color: 'var(--accent)' }}>{fmt(w?.balance_toman || 0)} ت</div>
          </div>
          {managed && (
            <div style={{ marginInlineStart: 'auto', display: 'flex', gap: 22, flexWrap: 'wrap' }}>
              <div><div style={{ fontSize: 12, color: 'var(--dim)' }}>واریزی</div><div style={{ fontWeight: 800, fontFamily: 'JetBrains Mono' }}>{fmt(w?.invested_toman || 0)} ت</div></div>
              <div><div style={{ fontSize: 12, color: 'var(--dim)' }}>سود</div><div style={{ fontWeight: 800, fontFamily: 'JetBrains Mono', color: (w?.profit_toman || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>{fmt(w?.profit_toman || 0)} ت</div></div>
            </div>
          )}
          <button onClick={withdraw} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '10px 18px', borderRadius: 11, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', fontSize: 13 }}>
            <ArrowUpFromLine size={16} /> برداشت
          </button>
        </div>

        {/* واریز کارت‌به‌کارت */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 800, fontSize: 16, marginBottom: 14 }}>
            <ArrowDownToLine size={18} style={{ color: 'var(--green)' }} /> واریز (کارت‌به‌کارت)
          </div>
          {pi && (pi.card_number || pi.account_number) && (
            <div style={{ background: 'var(--bg2)', borderRadius: 12, padding: 14, marginBottom: 16, fontSize: 13, lineHeight: 2 }}>
              {pi.card_number && <div>شماره کارت: <b style={{ fontFamily: 'JetBrains Mono' }} dir="ltr">{pi.card_number}</b>{pi.card_holder && ` — ${pi.card_holder}`}</div>}
              {pi.account_number && <div>شبا/حساب: <b style={{ fontFamily: 'JetBrains Mono' }} dir="ltr">{pi.account_number}</b></div>}
              <div style={{ color: 'var(--faint)', fontSize: 12 }}>پس از واریز، مبلغ و رسید را این‌جا ثبت کنید تا سوپر ادمین تأیید کند.</div>
            </div>
          )}
          {managed && w?.kyc_status !== 'verified' && (
            <div style={{ padding: 12, borderRadius: 10, background: 'rgba(251,191,36,0.1)', color: 'var(--amber)', fontSize: 13, marginBottom: 14 }}>
              برای سرمایه‌گذاری ابتدا باید احراز هویت شوید (صفحهٔ پروفایل).
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
            <div><div style={{ fontSize: 12, color: 'var(--dim)', marginBottom: 6 }}>مبلغ (تومان)</div><input style={input} value={amount} onChange={e => setAmount(e.target.value)} inputMode="numeric" /></div>
            <div><div style={{ fontSize: 12, color: 'var(--dim)', marginBottom: 6 }}>شماره پیگیری / ۴ رقم آخر کارت</div><input style={input} value={reference} onChange={e => setReference(e.target.value)} dir="ltr" /></div>
          </div>
          <div style={{ display: 'flex', gap: 12, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 14px', borderRadius: 10, border: '1px solid var(--border2)', cursor: 'pointer', fontSize: 13 }}>
              <Upload size={15} /> {receipt ? 'رسید انتخاب شد ✓' : 'بارگذاری رسید (اختیاری)'}
              <input type="file" accept="image/*" hidden onChange={pickReceipt} />
            </label>
            <button onClick={deposit} disabled={busy} style={{ marginInlineStart: 'auto', padding: '11px 26px', borderRadius: 11, border: 'none', background: 'var(--green)', color: '#05121a', fontWeight: 800, fontSize: 14, cursor: 'pointer', fontFamily: 'inherit' }}>
              ثبت واریز
            </button>
          </div>
        </div>

        {/* تاریخچه */}
        <div style={card}>
          <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 14 }}>تاریخچهٔ تراکنش‌ها</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ color: 'var(--dim)', textAlign: 'right' }}>
                {['نوع', 'مبلغ', 'وضعیت', 'توضیح', 'تاریخ'].map(c => <th key={c} style={{ padding: '8px 10px', fontWeight: 600 }}>{c}</th>)}
              </tr></thead>
              <tbody>
                {(w?.history || []).map((h, i) => {
                  const st = ST[h.status] || { t: h.status, c: 'var(--dim)' }
                  const isWd = h.kind === 'withdraw'
                  return (
                    <tr key={h.kind + h.id + i} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px', color: isWd ? 'var(--amber)' : 'var(--green)', fontWeight: 700 }}>{isWd ? '↑ برداشت' : '↓ واریز'}</td>
                      <td style={{ padding: '10px', fontFamily: 'JetBrains Mono' }}>{fmt(h.amount_toman)} ت{isWd && h.payout_toman ? <span style={{ color: 'var(--faint)', fontSize: 11 }}> (خالص {fmt(h.payout_toman)})</span> : null}</td>
                      <td style={{ padding: '10px', color: st.c, fontWeight: 700 }}>{st.t}</td>
                      <td style={{ padding: '10px', color: 'var(--dim)', fontSize: 12 }}>{h.reference || h.note || (h.purpose === 'invest' ? 'سرمایه‌گذاری' : '')}</td>
                      <td style={{ padding: '10px', fontSize: 12 }}>{h.created_at ? new Date(h.created_at).toLocaleDateString('fa-IR') : '—'}</td>
                    </tr>
                  )
                })}
                {(!w || w.history.length === 0) && <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--faint)' }}>تراکنشی ثبت نشده.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  )
}
