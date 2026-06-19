import { useState, useEffect, useRef, useCallback } from 'react'
import { User, ShieldCheck, ShieldAlert, ShieldQuestion, Camera, Upload, Loader2 } from 'lucide-react'
import Layout from '../components/Layout'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Profile {
  id: number; full_name: string; email: string | null; phone: string | null;
  national_id: string; birth_date: string; avatar: string; is_superadmin: boolean;
  kyc_status: string; kyc_match_score: number; kyc_note: string; kyc_submitted_at: string | null
}

const card: React.CSSProperties = { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }
const input: React.CSSProperties = { width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', color: 'var(--text)', fontSize: 14, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit' }
const label: React.CSSProperties = { fontSize: 12, color: 'var(--dim)', marginBottom: 6 }

const KYC_META: Record<string, { txt: string; color: string; Icon: any }> = {
  verified: { txt: 'تأییدشده', color: 'var(--green)', Icon: ShieldCheck },
  pending: { txt: 'در انتظار بررسی', color: 'var(--amber)', Icon: ShieldQuestion },
  rejected: { txt: 'ردشده', color: 'var(--red)', Icon: ShieldAlert },
  none: { txt: 'انجام‌نشده', color: 'var(--dim)', Icon: ShieldQuestion },
}

function fileToDataUri(file: File): Promise<string> {
  return new Promise((res, rej) => {
    const r = new FileReader()
    r.onload = () => res(r.result as string)
    r.onerror = rej
    r.readAsDataURL(file)
  })
}

export default function Profile() {
  const [p, setP] = useState<Profile | null>(null)
  const [fullName, setFullName] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [nationalId, setNationalId] = useState('')
  const [saving, setSaving] = useState(false)

  // KYC
  const [cardImg, setCardImg] = useState('')
  const [selfieImg, setSelfieImg] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [camOn, setCamOn] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const load = useCallback(async () => {
    try {
      const r = await api.get<Profile>('/profile/')
      setP(r.data); setFullName(r.data.full_name || ''); setBirthDate(r.data.birth_date || ''); setNationalId(r.data.national_id || '')
    } catch { /* ignore */ }
  }, [])
  useEffect(() => { load() }, [load])

  const saveProfile = async () => {
    setSaving(true)
    try {
      await api.put('/profile/', { full_name: fullName, birth_date: birthDate, national_id: nationalId })
      toast.success('پروفایل ذخیره شد'); load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'خطا') } finally { setSaving(false) }
  }

  const pickCard = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (f) setCardImg(await fileToDataUri(f))
  }

  const startCam = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
      streamRef.current = s; setCamOn(true)
      setTimeout(() => { if (videoRef.current) { videoRef.current.srcObject = s; videoRef.current.play() } }, 100)
    } catch { toast.error('دسترسی به دوربین ممکن نشد — می‌توانید عکس آپلود کنید') }
  }
  const stopCam = () => {
    streamRef.current?.getTracks().forEach(t => t.stop()); streamRef.current = null; setCamOn(false)
  }
  const capture = () => {
    const v = videoRef.current; if (!v) return
    const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d')!.drawImage(v, 0, 0)
    setSelfieImg(c.toDataURL('image/jpeg', 0.85)); stopCam()
  }
  const pickSelfie = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (f) setSelfieImg(await fileToDataUri(f))
  }
  useEffect(() => () => stopCam(), [])

  const submitKyc = async () => {
    if (!cardImg || !selfieImg) { toast.error('تصویر کارت ملی و سلفی الزامی است'); return }
    setSubmitting(true)
    try {
      const r = await api.post('/profile/kyc', { card_image: cardImg, selfie_image: selfieImg, national_id: nationalId, birth_date: birthDate })
      if (r.data.kyc_status === 'verified') toast.success('هویت شما تأیید شد ✅')
      else toast.success('مدارک ارسال شد؛ در انتظار بررسی.')
      setCardImg(''); setSelfieImg(''); load()
    } catch (e: any) { toast.error(e?.response?.data?.detail || 'خطا در ارسال') } finally { setSubmitting(false) }
  }

  const meta = KYC_META[p?.kyc_status || 'none'] || KYC_META.none
  const verified = p?.kyc_status === 'verified'

  return (
    <Layout title="پروفایل" subtitle="اطلاعات حساب و احراز هویت">
      <div style={{ maxWidth: 820, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* اطلاعات حساب */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
            <div style={{ width: 52, height: 52, borderRadius: 14, background: 'rgba(75,224,255,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <User size={26} style={{ color: 'var(--accent)' }} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 17 }}>{p?.full_name || '—'}</div>
              <div style={{ fontSize: 12, color: 'var(--dim)' }} dir="ltr">{p?.phone || p?.email || ''}</div>
            </div>
            <div style={{ marginInlineStart: 'auto', display: 'flex', alignItems: 'center', gap: 6, color: meta.color, fontWeight: 700, fontSize: 13 }}>
              <meta.Icon size={18} /> احراز هویت: {meta.txt}
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
            <div><div style={label}>نام و نام خانوادگی</div><input style={input} value={fullName} onChange={e => setFullName(e.target.value)} /></div>
            <div><div style={label}>کد ملی</div><input style={input} value={nationalId} onChange={e => setNationalId(e.target.value)} disabled={verified} dir="ltr" /></div>
            <div><div style={label}>تاریخ تولد</div><input style={input} value={birthDate} onChange={e => setBirthDate(e.target.value)} placeholder="۱۳۷۵/۰۵/۱۲" /></div>
          </div>
          <button onClick={saveProfile} disabled={saving} style={{ marginTop: 16, padding: '11px 24px', borderRadius: 11, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 800, fontSize: 14, cursor: 'pointer', fontFamily: 'inherit' }}>
            ذخیرهٔ پروفایل
          </button>
        </div>

        {/* احراز هویت */}
        {verified ? (
          <div style={{ ...card, borderColor: 'var(--green)', background: 'rgba(74,222,128,0.06)', display: 'flex', alignItems: 'center', gap: 12 }}>
            <ShieldCheck size={28} style={{ color: 'var(--green)' }} />
            <div>
              <div style={{ fontWeight: 800, color: 'var(--green)' }}>هویت شما تأیید شده است</div>
              <div style={{ fontSize: 12, color: 'var(--dim)', marginTop: 4 }}>{p?.kyc_note}</div>
            </div>
          </div>
        ) : (
          <div style={card}>
            <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 6 }}>احراز هویت با هوش مصنوعی</div>
            <div style={{ fontSize: 13, color: 'var(--dim)', lineHeight: 1.9, marginBottom: 16 }}>
              تصویر کارت ملی و یک سلفی از خودتان را ارسال کنید. هوش مصنوعی تطابق چهره را بررسی می‌کند.
            </div>
            {p?.kyc_status === 'pending' && (
              <div style={{ padding: 12, borderRadius: 10, background: 'rgba(251,191,36,0.1)', color: 'var(--amber)', fontSize: 13, marginBottom: 16 }}>
                ⏳ مدارک شما ارسال شده و در انتظار بررسی است. {p?.kyc_note}
              </div>
            )}
            {p?.kyc_status === 'rejected' && (
              <div style={{ padding: 12, borderRadius: 10, background: 'rgba(239,68,68,0.1)', color: 'var(--red)', fontSize: 13, marginBottom: 16 }}>
                مدارک قبلی تأیید نشد: {p?.kyc_note} — می‌توانید دوباره ارسال کنید.
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 18 }}>
              {/* کارت ملی */}
              <div>
                <div style={label}>۱) تصویر کارت ملی</div>
                <div style={{ height: 180, borderRadius: 12, border: '1px dashed var(--border2)', background: 'var(--bg2)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                  {cardImg ? <img src={cardImg} style={{ maxWidth: '100%', maxHeight: '100%' }} /> : <span style={{ color: 'var(--faint)', fontSize: 13 }}>تصویری انتخاب نشده</span>}
                </div>
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 10, padding: '8px 14px', borderRadius: 10, border: '1px solid var(--border2)', cursor: 'pointer', fontSize: 13 }}>
                  <Upload size={15} /> انتخاب تصویر
                  <input type="file" accept="image/*" hidden onChange={pickCard} />
                </label>
              </div>

              {/* سلفی */}
              <div>
                <div style={label}>۲) سلفی (عکس زنده از خودتان)</div>
                <div style={{ height: 180, borderRadius: 12, border: '1px dashed var(--border2)', background: 'var(--bg2)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                  {camOn ? <video ref={videoRef} style={{ maxWidth: '100%', maxHeight: '100%' }} muted playsInline />
                    : selfieImg ? <img src={selfieImg} style={{ maxWidth: '100%', maxHeight: '100%' }} />
                    : <span style={{ color: 'var(--faint)', fontSize: 13 }}>سلفی گرفته نشده</span>}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                  {!camOn ? (
                    <button onClick={startCam} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, border: '1px solid var(--accent)', background: 'transparent', color: 'var(--accent)', cursor: 'pointer', fontSize: 13, fontFamily: 'inherit' }}>
                      <Camera size={15} /> روشن‌کردن دوربین
                    </button>
                  ) : (
                    <button onClick={capture} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, cursor: 'pointer', fontSize: 13, fontFamily: 'inherit' }}>
                      <Camera size={15} /> گرفتن عکس
                    </button>
                  )}
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, border: '1px solid var(--border2)', cursor: 'pointer', fontSize: 13 }}>
                    <Upload size={15} /> آپلود عکس
                    <input type="file" accept="image/*" hidden onChange={pickSelfie} />
                  </label>
                </div>
              </div>
            </div>

            <button onClick={submitKyc} disabled={submitting || !cardImg || !selfieImg}
              style={{ marginTop: 18, width: '100%', padding: '13px', borderRadius: 12, border: 'none', background: (!cardImg || !selfieImg) ? 'var(--bg3)' : 'var(--accent)', color: (!cardImg || !selfieImg) ? 'var(--dim)' : '#05121a', fontWeight: 800, fontSize: 14, cursor: submitting ? 'wait' : 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
              {submitting ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> در حال بررسی با هوش مصنوعی…</> : 'ارسال برای احراز هویت'}
            </button>
          </div>
        )}
      </div>
    </Layout>
  )
}
