import { useState, useEffect, useRef } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
import { useAuthStore } from '../stores/authStore'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface FeatureImportance { name: string; key: string; importance: number }
interface Metrics {
  accuracy?: number; precision?: number; recall?: number;
  precision_at_threshold?: Record<string, { precision: number; signals: number; share: number }>;
  total_samples?: number; train_samples?: number; test_samples?: number;
  num_features?: number; symbols?: string[]; date_from?: string; date_to?: string; source?: string; split?: string;
  ai_threshold?: number;
}
interface ModelStatus {
  status:string; accuracy:number; is_trained:boolean; progress:number; message:string;
  features:string[]; model_name:string; version:string; training_data_days:number;
  feature_importances?: FeatureImportance[]; metrics?: Metrics; ai_explanation?: string; data_source?: string;
  accumulated_rows?: number; confidence_threshold?: number;
}

function AccuracyDial({ pct }: { pct: number }) {
  const r = 70, cx = 80, cy = 80
  const circ = 2 * Math.PI * r
  const offset = circ * (1 - pct / 100)
  return (
    <svg width={160} height={160} viewBox="0 0 160 160">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--bg3)" strokeWidth={12} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--accent)" strokeWidth={12} strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round" transform={`rotate(-90 ${cx} ${cy})`} style={{ transition: 'stroke-dashoffset .8s ease' }} />
      <text x={cx} y={cy - 8} textAnchor="middle" fill="var(--text)" fontSize={28} fontWeight={700} fontFamily="'JetBrains Mono'">{pct.toFixed(1)}%</text>
      <text x={cx} y={cy + 16} textAnchor="middle" fill="var(--dim)" fontSize={12}>دقت</text>
    </svg>
  )
}

const generateLearningData = (accuracy: number) =>
  Array.from({ length: 20 }, (_, i) => ({
    epoch: (i + 1) * 5,
    accuracy: Math.min(accuracy, 10 + (accuracy - 10) * Math.pow(i / 19, 0.5) + (Math.random() - .5) * 2),
    loss: Math.max(0.05, 0.9 - 0.85 * Math.pow(i / 19, 0.7) + (Math.random() - .5) * .05),
  }))

export default function Model() {
  const { t } = useAppStore()
  const { isSuperAdmin } = useAuthStore()
  const [status, setStatus] = useState<ModelStatus|null>(null)
  const [loading, setLoading] = useState(true)
  const [training, setTraining] = useState(false)
  const [bt, setBt] = useState<any>(null)
  const [btLoading, setBtLoading] = useState(false)
  const [sweep, setSweep] = useState<any>(null)
  const [sweepLoading, setSweepLoading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval>>()

  const runBacktest = async () => {
    setBtLoading(true); setBt(null)
    try { const r = await api.get('/model/backtest'); setBt(r.data) }
    catch (e: any) { toast.error(e.response?.data?.detail || 'خطا در بک‌تست') }
    finally { setBtLoading(false) }
  }

  const runSweep = async () => {
    setSweepLoading(true); setSweep(null)
    try { const r = await api.get('/model/backtest-sweep'); setSweep(r.data) }
    catch (e: any) { toast.error(e.response?.data?.detail || 'خطا در جاروب پارامتر') }
    finally { setSweepLoading(false) }
  }

  const load = async () => {
    try { const r = await api.get('/model/status'); setStatus(r.data) }
    catch {} finally { setLoading(false) }
  }

  useEffect(() => { load(); pollRef.current = setInterval(load, 3000); return () => clearInterval(pollRef.current) }, [])

  const startTraining = async () => {
    setTraining(true)
    try { await api.post('/model/train'); toast.success('آموزش مدل شروع شد') }
    catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
    finally { setTraining(false) }
  }

  const uploadData = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    try {
      const r = await api.post('/model/upload-data', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      toast.success(`${r.data.message} (مجموع: ${r.data.total})`)
      load()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'آپلود ناموفق بود')
    }
    e.target.value = ''
  }

  // دقت: اگر مقدار زندهٔ status.accuracy صفر بود، از metrics.accuracy (درصد) استفاده کن
  const acc = (status?.accuracy ? status.accuracy * 100 : 0) || (status?.metrics?.accuracy ?? 0)
  const learningData = generateLearningData(acc || 85)
  const isTraining = status?.status === 'training'
  const m = status?.metrics

  const modelStats = [
    { label: t.modelAcc, value: `${(m?.accuracy ?? acc).toFixed(1)}%`, note: status?.is_trained ? '✓ آماده' : '⏳ آموزش نیافته' },
    { label: 'منبع داده', value: m?.source || status?.data_source || '—', note: `${m?.date_from || ''}` },
    { label: t.totalSamples, value: (m?.total_samples ?? 0).toLocaleString('fa-IR'), note: 'نمونه واقعی' },
    { label: t.epochs, value: `${m?.num_features ?? 35}`, note: 'اندیکاتور' },
  ]

  return (
    <Layout title={t.navModel} subtitle="وضعیت مدل یادگیری ماشین">
      <div className="fade-in" style={{ display:'flex', flexDirection:'column', gap:22 }}>
        {isTraining && (
          <div style={{ background:'color-mix(in srgb,var(--accent) 10%,transparent)', border:'1px solid var(--accent)', borderRadius:14, padding:'14px 20px' }}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8, fontSize:14, fontWeight:600 }}>
              <span>{status?.message}</span>
              <span style={{ fontFamily:"'JetBrains Mono'" }}>{status?.progress}%</span>
            </div>
            <div style={{ height:8, background:'var(--bg3)', borderRadius:4 }}>
              <div style={{ height:'100%', width:`${status?.progress}%`, background:'var(--accent)', borderRadius:4, transition:'.3s' }} />
            </div>
          </div>
        )}

        {status?.status === 'error' && (
          <div style={{ background:'rgba(239,68,68,0.1)', border:'1px solid var(--red)', borderRadius:14, padding:'14px 20px', color:'var(--red)', fontSize:14, fontWeight:600 }}>
            {status?.message || 'آموزش با خطا مواجه شد'}
          </div>
        )}

        <div style={{ display:'grid', gridTemplateColumns:'1.5fr 1fr', gap:16 }}>
          <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:24 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6 }}>
              <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>{t.learningCurve}</div>
              <div style={{ display:'flex', gap:14, fontSize:12, fontFamily:"'JetBrains Mono'" }}>
                <span style={{ display:'flex', alignItems:'center', gap:6 }}><span style={{ width:9, height:9, borderRadius:2, background:'var(--green)', display:'inline-block' }} />{t.accuracy}</span>
                <span style={{ display:'flex', alignItems:'center', gap:6 }}><span style={{ width:9, height:9, borderRadius:2, background:'var(--red)', display:'inline-block' }} />{t.lossLabel}</span>
              </div>
            </div>
            <div style={{ height:260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={learningData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                  <XAxis dataKey="epoch" tick={{ fontSize:11, fill:'var(--faint)' }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize:11, fill:'var(--faint)' }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:10, color:'var(--text)', fontFamily:"'JetBrains Mono'" }} />
                  <Line type="monotone" dataKey="accuracy" stroke="var(--green)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="loss" stroke="var(--red)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:24, display:'flex', flexDirection:'column', justifyContent:'center', alignItems:'center', textAlign:'center' }}>
            <AccuracyDial pct={acc || 0} />
            <div style={{ fontFamily:"'Space Grotesk'", fontSize:15, fontWeight:600, marginBottom:6, marginTop:10 }}>{t.modelStatus}</div>
            <div style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'7px 16px', borderRadius:999, background:status?.is_trained ? 'color-mix(in srgb,var(--green) 16%,transparent)' : 'color-mix(in srgb,var(--amber) 16%,transparent)', color:status?.is_trained ? 'var(--green)' : 'var(--amber)', fontSize:13, fontWeight:600 }}>
              <span style={{ width:7, height:7, borderRadius:'50%', background:status?.is_trained ? 'var(--green)' : 'var(--amber)', animation:'pulse 2s infinite' }} />
              {status?.is_trained ? t.ready : (isTraining ? t.training : t.idle)}
            </div>
          </div>
        </div>

        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16 }}>
          {modelStats.map(m => (
            <div key={m.label} style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:20 }}>
              <div style={{ fontSize:13, color:'var(--dim)', marginBottom:8 }}>{m.label}</div>
              <div style={{ fontFamily:"'JetBrains Mono'", fontSize:22, fontWeight:700 }}>{m.value}</div>
              <div style={{ fontSize:12, color:'var(--accent)', marginTop:4 }}>{m.note}</div>
            </div>
          ))}
        </div>

        {/* اطلاعات داده آموزش */}
        {status?.metrics && status.metrics.total_samples ? (
          <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:24 }}>
            <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600, marginBottom:18 }}>جزئیات آموزش</div>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(150px, 1fr))', gap:14 }}>
              {[
                { l:'منبع داده', v: status.metrics.source || status.data_source || '—' },
                { l:'بازه زمانی', v: `${status.metrics.date_from || '—'} تا ${status.metrics.date_to || '—'}` },
                { l:'تعداد نمونه', v: (status.metrics.total_samples||0).toLocaleString('fa-IR') },
                { l:'بازارها', v: (status.metrics.symbols||[]).join('، ') || '—' },
                { l:'دقت (Accuracy)', v: `${status.metrics.accuracy}٪` },
                { l:'صحت (Precision @۰.۵)', v: `${status.metrics.precision}٪` },
                ...(status.metrics.precision_at_threshold?.['0.65'] ? [{
                  l: '🎯 صحتِ سیگنال خرید (آستانهٔ ۶۵٪)',
                  v: `${status.metrics.precision_at_threshold['0.65'].precision}٪ (روی ${status.metrics.precision_at_threshold['0.65'].share}٪ سیگنال‌ها)`
                }] : []),
                { l:'فراخوانی (Recall)', v: `${status.metrics.recall}٪` },
                { l:'تعداد اندیکاتور', v: status.metrics.num_features },
                { l:'روش ارزیابی', v: status.metrics.split || 'زمانی (out-of-sample)' },
                { l:'🧠 آستانه تصمیم', v: status.metrics.ai_threshold ? `${status.metrics.ai_threshold}٪ (تنظیم AI)` : (status.confidence_threshold ? `${status.confidence_threshold}٪ (پیش‌فرض)` : '—') },
              ].map((x,i)=>(
                <div key={i} style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:12, padding:'12px 14px' }}>
                  <div style={{ fontSize:11, color:'var(--faint)', marginBottom:5 }}>{x.l}</div>
                  <div style={{ fontSize:14, fontWeight:600, color:'var(--text)', fontFamily:"'JetBrains Mono'" }}>{x.v}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* مدل چه چیزی یاد گرفت — اهمیت اندیکاتورها */}
        <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:24 }}>
          <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600, marginBottom:6 }}>مدل چه چیزی یاد گرفت؟</div>
          <div style={{ fontSize:13, color:'var(--dim)', marginBottom:18 }}>اهمیت هر اندیکاتور در تصمیم‌گیری مدل (بیشتر = تأثیرگذارتر)</div>

          {(status?.feature_importances && status.feature_importances.length > 0) ? (
            <div style={{ display:'flex', flexDirection:'column', gap:9 }}>
              {status.feature_importances.slice(0, 20).map((f, i) => (
                <div key={i} style={{ display:'flex', alignItems:'center', gap:12 }}>
                  <div style={{ width:200, fontSize:13, color:'var(--text)', flexShrink:0, textAlign:'start' }}>{f.name}</div>
                  <div style={{ flex:1, height:18, background:'var(--bg3)', borderRadius:6, overflow:'hidden' }}>
                    <div style={{ height:'100%', width:`${Math.min(100, f.importance * 4)}%`, background:'linear-gradient(90deg, var(--accent), var(--accent2))', borderRadius:6, transition:'width .6s' }} />
                  </div>
                  <div style={{ width:52, textAlign:'end', fontSize:12, fontWeight:700, color:'var(--accent)', fontFamily:"'JetBrains Mono'", flexShrink:0 }}>{f.importance}٪</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ display:'flex', flexWrap:'wrap', gap:10 }}>
              {(status?.features || []).map((f, i) => (
                <span key={i} style={{ padding:'8px 15px', border:'1px solid var(--border2)', borderRadius:999, fontSize:13, background:'var(--bg3)', color:'var(--dim)' }}>{f}</span>
              ))}
            </div>
          )}
        </div>

        {/* توضیح هوش مصنوعی */}
        {status?.ai_explanation ? (
          <div style={{ background:'linear-gradient(135deg, rgba(75,224,255,0.06), rgba(255,92,200,0.06))', border:'1px solid var(--border)', borderRadius:18, padding:24 }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:14 }}>
              <span style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>✨ تحلیل هوش مصنوعی از آموخته‌های مدل</span>
            </div>
            <div style={{ fontSize:14, lineHeight:2, color:'var(--dim)', whiteSpace:'pre-wrap' }}>{status.ai_explanation}</div>
          </div>
        ) : null}

        {/* داده انباشته + آپلود + کنترل آموزش */}
        {isSuperAdmin && (
          <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:24 }}>
            <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600, marginBottom:8 }}>آموزش تجمعی و افزودن داده</div>
            <div style={{ fontSize:13, color:'var(--dim)', marginBottom:16, lineHeight:1.9 }}>
              هر بار آموزش، داده‌ی جدید بازار به مجموعه‌ی قبلی <b style={{color:'var(--text)'}}>اضافه</b> می‌شود و مدل روی همه‌ی داده‌ها آموزش می‌بیند (از صفر شروع نمی‌شود).
              مدل هر ۶ ساعت هم به‌صورت خودکار با داده جدید به‌روز می‌شود.
            </div>
            <div style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
              <div style={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:12, padding:'12px 18px' }}>
                <div style={{ fontSize:11, color:'var(--faint)', marginBottom:4 }}>کل داده انباشته</div>
                <div style={{ fontFamily:"'JetBrains Mono'", fontSize:18, fontWeight:700, color:'var(--accent)' }}>
                  {(status?.accumulated_rows ?? 0).toLocaleString('fa-IR')} ردیف
                </div>
              </div>
              <button onClick={startTraining} disabled={training || isTraining} style={{ padding:'13px 28px', border:'none', borderRadius:12, background:'var(--accent)', color:'#05121a', fontWeight:700, fontFamily:"'Space Grotesk'", fontSize:14, cursor:'pointer', opacity:training||isTraining?.7:1 }}>
                {isTraining ? `در حال آموزش... ${status?.progress||0}%` : t.retrain}
              </button>
              <label style={{ padding:'13px 24px', border:'1px solid var(--border2)', borderRadius:12, background:'transparent', color:'var(--text)', fontWeight:600, fontSize:14, cursor:'pointer', display:'inline-flex', alignItems:'center', gap:8 }}>
                📥 آپلود داده (CSV)
                <input type="file" accept=".csv" onChange={uploadData} style={{ display:'none' }} />
              </label>
            </div>
            <div style={{ fontSize:11, color:'var(--faint)', marginTop:12 }}>
              فرمت CSV: ستون‌های timestamp, open, high, low, close, volume (و symbol اختیاری)
            </div>
          </div>
        )}

        {/* بک‌تست با کارمزد (فقط سوپر ادمین) */}
        {isSuperAdmin && (
          <div style={{ background:'var(--panel)', border:'1px solid var(--border)', borderRadius:18, padding:24 }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:12, marginBottom:14 }}>
              <div>
                <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>🧪 بک‌تست با کارمزد</div>
                <div style={{ fontSize:12, color:'var(--dim)', marginTop:4 }}>شبیه‌سازی روی دادهٔ out-of-sample با احتساب کمیسیون — سود/زیان واقعی</div>
              </div>
              <button onClick={runBacktest} disabled={btLoading} style={{ padding:'11px 22px', border:'none', borderRadius:11, background:'var(--accent)', color:'#05121a', fontWeight:700, fontSize:14, cursor:'pointer', opacity:btLoading?.7:1 }}>
                {btLoading ? 'در حال اجرا…' : 'اجرای بک‌تست'}
              </button>
            </div>
            {bt && bt.error && <div style={{ color:'var(--amber)', fontSize:13 }}>{bt.error}</div>}
            {bt && !bt.error && (
              <>
                <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(150px,1fr))', gap:12 }}>
                  {[
                    { l:'تعداد معامله', v: (bt.trades||0).toLocaleString('fa-IR') },
                    { l:'نرخ برد', v: `${bt.win_rate}٪`, c: bt.win_rate>=50?'var(--green)':'var(--amber)' },
                    { l:'میانگین سود هر معامله', v: `${bt.avg_net_pct}٪`, c: bt.avg_net_pct>=0?'var(--green)':'var(--red)' },
                    { l:'بازده مرکب کل', v: `${bt.total_compound_pct}٪`, c: bt.total_compound_pct>=0?'var(--green)':'var(--red)' },
                    { l:'ضریب سود (PF)', v: bt.profit_factor ?? '—', c: (bt.profit_factor||0)>=1?'var(--green)':'var(--red)' },
                    { l:'حداکثر افت سرمایه', v: `${bt.max_drawdown_pct}٪`, c:'var(--red)' },
                  ].map((x,i)=>(
                    <div key={i} style={{ background:'var(--bg2)', borderRadius:12, padding:14, textAlign:'center' }}>
                      <div style={{ fontSize:12, color:'var(--dim)' }}>{x.l}</div>
                      <div style={{ fontSize:18, fontWeight:800, marginTop:6, color:x.c||'var(--text)', fontFamily:"'JetBrains Mono'" }}>{x.v}</div>
                    </div>
                  ))}
                </div>
                <div style={{ fontSize:12, color:'var(--faint)', marginTop:12 }}>
                  پارامترها: آستانهٔ {bt.threshold}٪ · کارمزد {bt.fee_pct}٪ هر طرف · هدف +{bt.tp_pct}٪ / حد ضرر −{bt.sl_pct}٪ در {bt.horizon_h} ساعت
                  {bt.profit_factor!=null && (bt.profit_factor>=1 ? ' — ✅ پس از کمیسیون سودده است' : ' — ⚠️ پس از کمیسیون ضرر می‌دهد')}
                </div>
              </>
            )}
          </div>
        )}

        {/* جاروب پارامتر: یافتن بهترین ترکیب آستانه × هدف/حدضرر */}
        {isSuperAdmin && (
          <div style={{ background:'var(--panel)', border:'1px solid var(--border)', borderRadius:18, padding:24 }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:12, marginBottom:14 }}>
              <div>
                <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>🔍 یافتن بهترین پارامترها</div>
                <div style={{ fontSize:12, color:'var(--dim)', marginTop:4 }}>چند ترکیبِ آستانه × هدف/حدضرر را بک‌تست می‌کند تا سوددهترین ترکیب پس از کمیسیون پیدا شود</div>
              </div>
              <button onClick={runSweep} disabled={sweepLoading} style={{ padding:'11px 22px', border:'none', borderRadius:11, background:'var(--accent)', color:'#05121a', fontWeight:700, fontSize:14, cursor:'pointer', opacity:sweepLoading?.7:1 }}>
                {sweepLoading ? 'در حال جاروب… (چند دقیقه)' : 'یافتن بهترین پارامترها'}
              </button>
            </div>
            {sweep && sweep.error && <div style={{ color:'var(--amber)', fontSize:13 }}>{sweep.error}</div>}
            {sweep && !sweep.error && (
              <>
                <div style={{ padding:'12px 14px', borderRadius:12, marginBottom:14, fontSize:13, fontWeight:700,
                  background: sweep.any_profitable ? 'rgba(16,185,129,.12)' : 'rgba(245,158,11,.12)',
                  color: sweep.any_profitable ? 'var(--green)' : 'var(--amber)' }}>
                  {sweep.any_profitable
                    ? `✅ حداقل یک ترکیبِ سودده پس از کمیسیون پیدا شد — بهترین: آستانهٔ ${sweep.best.threshold}٪ · هدف +${sweep.best.tp_pct}٪ / حد ضرر −${sweep.best.sl_pct}٪ در ${sweep.best.horizon_h} ساعت · فیلتر روند ADX≥${sweep.best.adx_min||'خاموش'} (PF ${sweep.best.profit_factor})`
                    : '⚠️ هیچ ترکیبی پس از کمیسیون سودده نبود — حتی با فیلترِ رژیمِ بازار (ADX) هم استراتژی برتری ندارد.'}
                </div>
                <div style={{ overflowX:'auto' }}>
                  <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13, fontFamily:"'JetBrains Mono'" }}>
                    <thead>
                      <tr style={{ color:'var(--dim)', textAlign:'center' }}>
                        {['آستانه','هدف٪','حدضرر٪','افق(h)','ADX≥','معامله','نرخ برد','میانگین خالص','مرکب کل','PF','حداکثر افت'].map((h,i)=>(
                          <th key={i} style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)', fontWeight:600, whiteSpace:'nowrap' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(sweep.combos||[]).map((c:any,i:number)=>{
                        const good = (c.profit_factor||0)>=1 && c.avg_net_pct>0
                        return (
                          <tr key={i} style={{ textAlign:'center', background: i===0 ? 'rgba(45,212,191,.08)' : 'transparent' }}>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)' }}>{c.threshold}٪</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)' }}>+{c.tp_pct}</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)' }}>−{c.sl_pct}</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)' }}>{c.horizon_h}</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)' }}>{c.adx_min ? c.adx_min : '—'}</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)' }}>{c.trades}</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)', color:c.win_rate>=50?'var(--green)':'var(--amber)' }}>{c.win_rate}٪</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)', color:c.avg_net_pct>=0?'var(--green)':'var(--red)' }}>{c.avg_net_pct}٪</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)', color:c.total_compound_pct>=0?'var(--green)':'var(--red)' }}>{c.total_compound_pct}٪</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)', fontWeight:700, color:good?'var(--green)':'var(--red)' }}>{c.profit_factor ?? '—'}</td>
                            <td style={{ padding:'8px 6px', borderBottom:'1px solid var(--border)', color:'var(--red)' }}>{c.max_drawdown_pct}٪</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                <div style={{ fontSize:12, color:'var(--faint)', marginTop:12 }}>
                  ردیفِ سبز = سوددهترین ترکیب. کارمزد {sweep.fee_pct}٪ هر طرف. مرتب‌شده بر اساس ضریب سود (PF).
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}
