import { useState, useEffect, useCallback } from 'react'
import { Check, X, Eye, ShieldCheck } from 'lucide-react'
import Layout from '../components/Layout'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Dep { id: number; user_id: number; user_name: string; user_phone: string; amount_toman: number; purpose: string; reference: string; has_receipt: boolean; status: string; note: string; created_at: string | null }
interface Kyc { id: number; full_name: string; phone: string; national_id: string; birth_date: string; kyc_status: string; kyc_match_score: number; kyc_note: string; kyc_submitted_at: string | null }

const card: React.CSSProperties = { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }
const fmt = (n: number) => Math.round(n || 0).toLocaleString('en-US')
const btn = (c: string): React.CSSProperties => ({ background: 'transparent', border: `1px solid ${c}`, color: c, borderRadius: 8, padding: '5px 10px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 4 })

export default function AdminWallet() {
  const [deps, setDeps] = useState<Dep[]>([])
  const [kyc, setKyc] = useState<Kyc[]>([])
  const [modal, setModal] = useState<{ title: string; imgs: string[]; video?: string; challenge?: string } | null>(null)

  const load = useCallback(async () => {
    try {
      const [d, k] = await Promise.all([
        api.get<Dep[]>('/wallet/admin/deposits'),
        api.get<Kyc[]>('/profile/admin/kyc?status=pending'),
      ])
      setDeps(d.data); setKyc(k.data)
    } catch { toast.error('خطا در بارگذاری') }
  }, [])
  useEffect(() => { load() }, [load])

  const decideDep = async (d: Dep, approve: boolean) => {
    let note = ''
    if (!approve) { note = prompt('علت رد (اختیاری):', '') || '' }
    try { await api.post(`/wallet/admin/deposits/${d.id}/decide`, { approve, note }); toast.success(approve ? 'تأیید شد' : 'رد شد'); load() } catch (e: any) { toast.error(e?.response?.data?.detail || 'خطا') }
  }
  const viewReceipt = async (d: Dep) => {
    try { const r = await api.get(`/wallet/admin/deposits/${d.id}/receipt`); setModal({ title: `رسید واریز ${d.user_name}`, imgs: [r.data.receipt_image].filter(Boolean) }) } catch { toast.error('خطا') }
  }

  const decideKyc = async (k: Kyc, approve: boolean) => {
    let note = ''
    if (!approve) { note = prompt('علت رد:', '') || '' }
    try { await api.post(`/profile/admin/kyc/${k.id}/decide`, { approve, note }); toast.success(approve ? 'تأیید شد' : 'رد شد'); load() } catch { toast.error('خطا') }
  }
  const viewKyc = async (k: Kyc) => {
    try { const r = await api.get(`/profile/admin/kyc/${k.id}/images`); setModal({ title: `مدارک ${k.full_name}`, imgs: [r.data.card_image].filter(Boolean), video: r.data.video, challenge: r.data.challenge }) } catch { toast.error('خطا') }
  }

  const ST: Record<string, { t: string; c: string }> = { pending: { t: 'در انتظار', c: 'var(--amber)' }, approved: { t: 'تأییدشده', c: 'var(--green)' }, rejected: { t: 'ردشده', c: 'var(--red)' } }

  return (
    <Layout title="واریز و احراز هویت" subtitle="تأیید واریزها و مدارک احراز هویت کاربران">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* احراز هویت در انتظار */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 800, fontSize: 16, marginBottom: 14 }}>
            <ShieldCheck size={18} style={{ color: 'var(--accent)' }} /> احراز هویت در انتظار بررسی
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ color: 'var(--dim)', textAlign: 'right' }}>
                {['کاربر', 'کد ملی', 'تطابق AI', 'یادداشت', 'عملیات'].map(c => <th key={c} style={{ padding: '8px 10px', fontWeight: 600 }}>{c}</th>)}
              </tr></thead>
              <tbody>
                {kyc.map(k => (
                  <tr key={k.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '10px' }}>{k.full_name}<div style={{ fontSize: 11, color: 'var(--faint)' }} dir="ltr">{k.phone}</div></td>
                    <td style={{ padding: '10px', fontFamily: 'JetBrains Mono' }} dir="ltr">{k.national_id || '—'}</td>
                    <td style={{ padding: '10px', fontWeight: 700, color: k.kyc_match_score >= 80 ? 'var(--green)' : k.kyc_match_score >= 50 ? 'var(--amber)' : 'var(--red)' }}>{k.kyc_match_score}٪</td>
                    <td style={{ padding: '10px', fontSize: 12, color: 'var(--dim)', maxWidth: 240 }}>{k.kyc_note}</td>
                    <td style={{ padding: '10px' }}>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => viewKyc(k)} style={btn('var(--accent)')}><Eye size={14} /> مدارک</button>
                        <button onClick={() => decideKyc(k, true)} style={btn('var(--green)')}><Check size={14} /></button>
                        <button onClick={() => decideKyc(k, false)} style={btn('var(--red)')}><X size={14} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
                {kyc.length === 0 && <tr><td colSpan={5} style={{ padding: 20, textAlign: 'center', color: 'var(--faint)' }}>موردی در انتظار نیست.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* واریزها */}
        <div style={card}>
          <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 14 }}>💳 واریزهای کارت‌به‌کارت</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead><tr style={{ color: 'var(--dim)', textAlign: 'right' }}>
                {['کاربر', 'مبلغ', 'نوع', 'پیگیری', 'وضعیت', 'عملیات'].map(c => <th key={c} style={{ padding: '8px 10px', fontWeight: 600 }}>{c}</th>)}
              </tr></thead>
              <tbody>
                {deps.map(d => {
                  const st = ST[d.status] || { t: d.status, c: 'var(--dim)' }
                  return (
                    <tr key={d.id} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px' }}>{d.user_name}<div style={{ fontSize: 11, color: 'var(--faint)' }} dir="ltr">{d.user_phone}</div></td>
                      <td style={{ padding: '10px', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>{fmt(d.amount_toman)} ت</td>
                      <td style={{ padding: '10px', fontSize: 12 }}>{d.purpose === 'invest' ? 'سرمایه‌گذاری' : d.purpose === 'withdraw' ? 'برداشت' : 'کیف پول'}</td>
                      <td style={{ padding: '10px', fontSize: 12 }} dir="ltr">{d.reference || '—'}</td>
                      <td style={{ padding: '10px', color: st.c, fontWeight: 700 }}>{st.t}</td>
                      <td style={{ padding: '10px' }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          {d.has_receipt && <button onClick={() => viewReceipt(d)} style={btn('var(--accent)')}><Eye size={14} /> رسید</button>}
                          {d.status === 'pending' && <>
                            <button onClick={() => decideDep(d, true)} style={btn('var(--green)')}><Check size={14} /></button>
                            <button onClick={() => decideDep(d, false)} style={btn('var(--red)')}><X size={14} /></button>
                          </>}
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {deps.length === 0 && <tr><td colSpan={6} style={{ padding: 20, textAlign: 'center', color: 'var(--faint)' }}>واریزی ثبت نشده.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {modal && (
        <div onClick={() => setModal(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
          <div onClick={e => e.stopPropagation()} style={{ ...card, maxWidth: 720, width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ fontWeight: 800 }}>{modal.title}</div>
              <button onClick={() => setModal(null)} style={btn('var(--red)')}><X size={16} /></button>
            </div>
            {modal.challenge && (
              <div style={{ marginBottom: 12, padding: 12, borderRadius: 10, background: 'var(--bg2)', border: '1px solid var(--accent)' }}>
                <span style={{ fontSize: 12, color: 'var(--dim)' }}>عبارتی که کاربر باید در ویدئو گفته باشد: </span>
                <b style={{ color: 'var(--accent)', fontFamily: 'JetBrains Mono' }}>{modal.challenge}</b>
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {modal.imgs.map((src, i) => (
                <div key={i}><div style={{ fontSize: 12, color: 'var(--dim)', marginBottom: 6 }}>کارت ملی</div><img src={src} style={{ width: '100%', borderRadius: 10, border: '1px solid var(--border)' }} /></div>
              ))}
              {modal.video && (
                <div><div style={{ fontSize: 12, color: 'var(--dim)', marginBottom: 6 }}>ویدئوی احراز هویت (صدا را بررسی کنید)</div>
                  <video src={modal.video} controls playsInline style={{ width: '100%', borderRadius: 10, border: '1px solid var(--border)' }} /></div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  )
}
