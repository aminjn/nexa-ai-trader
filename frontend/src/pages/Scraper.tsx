import { useState, useEffect } from 'react'
import { Globe, Plus, Trash2, Play, Eye, RefreshCw, MousePointerClick } from 'lucide-react'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
import { useAuthStore } from '../stores/authStore'
import api from '../lib/api'
import toast from 'react-hot-toast'

interface Source {
  id: number
  name: string
  url: string
  selector: string
  use_proxy: boolean
  enabled: boolean
  last_value: string
  last_scraped: string | null
}

export default function Scraper() {
  const { t } = useAppStore()
  const token = useAuthStore(s => s.token)
  const [pickerUrl, setPickerUrl] = useState('')
  const [capturedFields, setCapturedFields] = useState<{name:string; selector:string; sample:string}[]>([])
  const [linkSelector, setLinkSelector] = useState('')
  const [inDetail, setInDetail] = useState(false)
  const [lastPick, setLastPick] = useState<{selector:string; text:string; href:string}|null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)

  // فرم افزودن
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [selector, setSelector] = useState('')
  const [useProxy, setUseProxy] = useState(false)
  const [adding, setAdding] = useState(false)
  const [testing, setTesting] = useState(false)
  const [preview, setPreview] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [groups, setGroups] = useState<{label:string; selector:string; count:number; samples:string[]}[]>([])
  const [analyzeErr, setAnalyzeErr] = useState('')

  const analyzePage = async () => {
    if (!url.trim()) { toast.error('آدرس سایت را وارد کنید'); return }
    setAnalyzing(true); setGroups([]); setAnalyzeErr('')
    try {
      const r = await api.post('/scraper/analyze', { url: url.trim(), use_proxy: useProxy })
      if (r.data.ok) {
        setGroups(r.data.groups || [])
        if ((r.data.groups || []).length === 0) setAnalyzeErr('چیزی پیدا نشد')
      } else setAnalyzeErr(r.data.error || 'خطا')
    } catch (e: any) { setAnalyzeErr(e.response?.data?.detail || 'خطا در تحلیل صفحه') }
    finally { setAnalyzing(false) }
  }

  const pickGroup = (g: {label:string; selector:string}) => {
    setSelector(g.selector)
    if (!name.trim()) setName(g.label)
    setPreview('');
    toast.success(`«${g.label}» انتخاب شد — حالا «افزودن منبع» را بزنید`)
  }

  const load = async () => {
    try { const r = await api.get('/scraper/sources'); setSources(r.data || []) }
    catch {} finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  // دریافت انتخاب از داخل قاب (کلیک بصری)
  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.data && e.data.type === 'nexa-pick') {
        setLastPick({ selector: e.data.selector || '', text: e.data.text || '', href: e.data.href || '' })
      }
    }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [])

  // وقتی روی صفحه‌ی مطلب هستیم، هر کلیک = فیلد محتوا
  useEffect(() => {
    if (!lastPick) return
    if (inDetail) {
      setCapturedFields(prev => {
        const defaultName = prev.length === 0 ? 'محتوا' : `فیلد ${prev.length + 1}`
        return [...prev, { name: defaultName, selector: lastPick.selector, sample: lastPick.text }]
      })
      toast.success('فیلد محتوا اضافه شد ✓')
      setLastPick(null)
    }
  }, [lastPick, inDetail])

  const followLink = () => {
    if (!lastPick?.href) { toast.error('این مورد لینک ندارد'); return }
    setLinkSelector(lastPick.selector)
    const q = new URLSearchParams({ url: lastPick.href, token: token || '', use_proxy: String(useProxy) })
    setPickerUrl(`/api/scraper/proxy?${q.toString()}`)
    setInDetail(true)
    setLastPick(null)
    toast.success('وارد صفحه مطلب شدی — حالا روی محتوا کلیک کن')
  }

  const addListField = () => {
    if (!lastPick) return
    setCapturedFields(prev => [...prev, { name: prev.length === 0 ? 'عنوان' : `فیلد ${prev.length + 1}`, selector: lastPick.selector, sample: lastPick.text }])
    setLastPick(null)
    toast.success('فیلد اضافه شد ✓')
  }

  const openPicker = () => {
    if (!url.trim()) { toast.error('آدرس سایت را وارد کنید'); return }
    const q = new URLSearchParams({ url: url.trim(), token: token || '', use_proxy: String(useProxy) })
    setPickerUrl(`/api/scraper/proxy?${q.toString()}`)
    setInDetail(false); setLinkSelector(''); setCapturedFields([]); setLastPick(null)
  }

  const testScrape = async () => {
    if (!url.trim()) { toast.error('آدرس سایت را وارد کنید'); return }
    setTesting(true); setPreview('')
    try {
      const fields = capturedFields.map(f => ({ name: f.name, selector: f.selector }))
      const r = await api.post('/scraper/test-recipe', {
        url: url.trim(), selector: selector.trim(), link_selector: linkSelector, fields, use_proxy: useProxy
      })
      setPreview(r.data.preview || '')
    } catch (e: any) { toast.error(e.response?.data?.detail || 'خطا در تست') }
    finally { setTesting(false) }
  }

  const addSource = async () => {
    if (!name.trim() || !url.trim()) { toast.error('نام و آدرس الزامی است'); return }
    const fields = capturedFields.map(f => ({ name: f.name, selector: f.selector }))
    if (fields.length === 0 && !selector.trim()) { toast.error('حداقل یک فیلد انتخاب کن'); return }
    setAdding(true)
    try {
      await api.post('/scraper/sources', { name: name.trim(), url: url.trim(), selector: selector.trim(), link_selector: linkSelector, fields, use_proxy: useProxy })
      toast.success('منبع اضافه شد')
      setName(''); setUrl(''); setSelector(''); setUseProxy(false); setPreview(''); setCapturedFields([]); setPickerUrl(''); setLinkSelector(''); setInDetail(false)
      load()
    } catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
    finally { setAdding(false) }
  }

  const del = async (id: number) => {
    if (!window.confirm('حذف شود؟')) return
    try { await api.delete(`/scraper/sources/${id}`); load() } catch {}
  }
  const toggle = async (id: number) => {
    try { await api.put(`/scraper/sources/${id}/toggle`); load() } catch {}
  }
  const runAll = async () => {
    setRunning(true)
    try { const r = await api.post('/scraper/run'); toast.success(r.data.message); load() }
    catch (e: any) { toast.error(e.response?.data?.detail || 'خطا') }
    finally { setRunning(false) }
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10,
    padding: '10px 14px', color: 'var(--text)', fontSize: 14, outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit',
  }
  const label: React.CSSProperties = { color: 'var(--faint)', fontSize: 12, marginBottom: 6, fontWeight: 600 }
  const card: React.CSSProperties = { background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }

  return (
    <Layout title="اسکرپر سایت‌ها" subtitle="افزودن هر سایت برای جمع‌آوری داده و اخبار جهت تحلیل فاندامنتال">
      <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>

        {/* فرم افزودن */}
        <div style={card}>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, marginBottom: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Plus size={18} style={{ color: 'var(--accent)' }} /> افزودن منبع جدید
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div><div style={label}>نام منبع</div>
              <input style={inputStyle} value={name} onChange={e => setName(e.target.value)} placeholder="مثلاً اخبار ارزدیجیتال" /></div>
            <div><div style={label}>آدرس سایت (URL)</div>
              <input style={inputStyle} value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..." dir="ltr" /></div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 14, flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 14 }}>
              <input type="checkbox" checked={useProxy} onChange={e => setUseProxy(e.target.checked)} />
              سایت خارجی است (از پروکسی استفاده کن)
            </label>
            <button onClick={openPicker} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '11px 22px', borderRadius: 11, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
              <MousePointerClick size={15} /> باز کردن سایت و انتخاب با کلیک
            </button>
            <button onClick={analyzePage} disabled={analyzing} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '11px 22px', borderRadius: 11, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--text)', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
              <RefreshCw size={15} style={{ animation: analyzing ? 'spin 1s linear infinite' : 'none' }} /> {analyzing ? 'در حال تحلیل...' : 'تشخیص خودکار گزینه‌ها'}
            </button>
          </div>

          {analyzeErr && <div style={{ marginTop: 12, color: 'var(--red)', fontSize: 13 }}>{analyzeErr}</div>}

          {/* انتخابگر بصری: سایت داخل قاب */}
          {pickerUrl && (
            <div style={{ marginTop: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>
                  {inDetail ? '📄 مرحله ۲: روی محتوای داخل مطلب کلیک کن' : '📰 مرحله ۱: روی عنوان یک مطلب کلیک کن'}
                </span>
                <button onClick={() => { setPickerUrl(''); setInDetail(false) }} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 8, padding: '4px 12px', color: 'var(--dim)', cursor: 'pointer', fontSize: 12 }}>بستن</button>
              </div>

              {/* اقدام پس از کلیک (مرحله ۱: انتخاب لینک عنوان) */}
              {lastPick && !inDetail && (
                <div style={{ marginBottom: 10, padding: 12, background: 'color-mix(in srgb, var(--accent) 10%, var(--bg2))', border: '1px solid var(--accent)', borderRadius: 10 }}>
                  <div style={{ fontSize: 13, color: 'var(--text)', marginBottom: 8 }}>انتخاب شد: <b>{lastPick.text}</b></div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {lastPick.href && (
                      <button onClick={followLink} style={{ padding: '9px 16px', borderRadius: 10, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                        ✅ ورود به مطلب و انتخاب محتوا
                      </button>
                    )}
                    <button onClick={addListField} style={{ padding: '9px 16px', borderRadius: 10, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--text)', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
                      افزودن به‌عنوان فیلد (بدون ورود)
                    </button>
                  </div>
                </div>
              )}

              <iframe src={pickerUrl} title="picker" style={{ width: '100%', height: 460, border: '1px solid var(--border2)', borderRadius: 12, background: '#fff' }} />
            </div>
          )}

          {/* فیلدهای انتخاب‌شده (رسپی چندمرحله‌ای) */}
          {capturedFields.length > 0 && (
            <div style={{ marginTop: 16, padding: 16, background: 'var(--bg2)', border: '1px solid var(--accent)', borderRadius: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)', marginBottom: 12 }}>فیلدهای انتخاب‌شده ({capturedFields.length}):</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {capturedFields.map((f, i) => (
                  <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <input value={f.name} onChange={e => setCapturedFields(prev => prev.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
                      style={{ width: 120, background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', color: 'var(--text)', fontSize: 13, fontFamily: 'inherit' }} placeholder="نام فیلد" />
                    <div style={{ flex: 1, fontSize: 12, color: 'var(--dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.sample}</div>
                    <button onClick={() => setCapturedFields(prev => prev.filter((_, j) => j !== i))} style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, width: 32, height: 32, cursor: 'pointer', color: '#ef4444' }}><Trash2 size={13} /></button>
                  </div>
                ))}
              </div>
              <div style={{ fontSize: 12, color: 'var(--faint)', marginTop: 10 }}>
                می‌تونی چند فیلد انتخاب کنی (عنوان، محتوا، تاریخ...). بعد نام منبع را بنویس و «افزودن منبع» را بزن.
              </div>
            </div>
          )}

          {/* گزینه‌های تشخیص‌داده‌شده */}
          {groups.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 13, color: 'var(--dim)', marginBottom: 10 }}>روی گزینه‌ای که می‌خواهی استخراج شود کلیک کن:</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                {groups.map((g, i) => (
                  <div key={i} onClick={() => pickGroup(g)}
                    style={{ cursor: 'pointer', padding: 14, borderRadius: 12, background: selector === g.selector ? 'color-mix(in srgb, var(--accent) 14%, var(--bg2))' : 'var(--bg2)', border: `1px solid ${selector === g.selector ? 'var(--accent)' : 'var(--border)'}`, transition: '.15s' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontWeight: 700, color: 'var(--text)' }}>{g.label}</span>
                      <span style={{ fontSize: 11, color: 'var(--faint)' }}>{g.count} مورد</span>
                    </div>
                    {g.samples.slice(0, 3).map((s, j) => (
                      <div key={j} style={{ fontSize: 12, color: 'var(--dim)', lineHeight: 1.6, marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>• {s}</div>
                    ))}
                    {selector === g.selector && <div style={{ marginTop: 6, fontSize: 11, color: 'var(--accent)', fontWeight: 700 }}>✓ انتخاب شد</div>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CSS selector دستی (پیشرفته) */}
          <details style={{ marginTop: 16 }}>
            <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--faint)' }}>تنظیم پیشرفته (CSS Selector دستی)</summary>
            <input style={{ ...inputStyle, marginTop: 8 }} value={selector} onChange={e => setSelector(e.target.value)} placeholder="مثلاً .news-title یا h2 یا .price" dir="ltr" />
          </details>

          <div style={{ display: 'flex', gap: 10, marginTop: 18, flexWrap: 'wrap' }}>
            <button onClick={testScrape} disabled={testing} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '11px 20px', borderRadius: 11, border: '1px solid var(--border2)', background: 'transparent', color: 'var(--text)', fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
              <Eye size={15} /> {testing ? 'در حال تست...' : 'تست استخراج'}
            </button>
            <button onClick={addSource} disabled={adding} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '11px 24px', borderRadius: 11, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
              <Plus size={15} /> {adding ? 'در حال افزودن...' : 'افزودن منبع'}
            </button>
          </div>

          {preview && (
            <div style={{ marginTop: 16, padding: 16, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12 }}>
              <div style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 8 }}>پیش‌نمایش استخراج:</div>
              <div style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.8, maxHeight: 200, overflowY: 'auto', whiteSpace: 'pre-wrap' }}>{preview}</div>
            </div>
          )}
        </div>

        {/* لیست منابع */}
        <div style={card}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
            <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Globe size={18} style={{ color: 'var(--accent)' }} /> منابع ({sources.length})
            </div>
            <button onClick={runAll} disabled={running} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', borderRadius: 11, border: 'none', background: 'var(--accent)', color: '#05121a', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'inherit' }}>
              <RefreshCw size={14} style={{ animation: running ? 'spin 1s linear infinite' : 'none' }} /> اسکرپ همه الان
            </button>
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', color: 'var(--dim)', padding: 30 }}>در حال بارگذاری...</div>
          ) : sources.length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--faint)', padding: 30, fontSize: 14 }}>هنوز منبعی اضافه نشده. از فرم بالا اضافه کنید.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {sources.map(s => (
                <div key={s.id} style={{ padding: 16, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: 200 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontWeight: 700, color: 'var(--text)' }}>{s.name}</span>
                        <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: s.enabled ? 'rgba(74,222,128,0.12)' : 'rgba(148,163,184,0.1)', color: s.enabled ? 'var(--green)' : 'var(--dim)', border: `1px solid ${s.enabled ? 'var(--green)' : 'var(--border)'}` }}>{s.enabled ? 'فعال' : 'غیرفعال'}</span>
                        {s.use_proxy && <span style={{ fontSize: 11, color: 'var(--amber)' }}>پروکسی</span>}
                      </div>
                      <div style={{ fontSize: 12, color: 'var(--dim)', fontFamily: "'JetBrains Mono'", marginTop: 4, direction: 'ltr', textAlign: 'start', wordBreak: 'break-all' }}>{s.url}</div>
                      {s.selector && <div style={{ fontSize: 11, color: 'var(--faint)', fontFamily: "'JetBrains Mono'", marginTop: 2, direction: 'ltr', textAlign: 'start' }}>selector: {s.selector}</div>}
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => toggle(s.id)} title="فعال/غیرفعال" style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 9, width: 36, height: 36, cursor: 'pointer', color: 'var(--dim)' }}><Play size={14} /></button>
                      <button onClick={() => del(s.id)} title="حذف" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 9, width: 36, height: 36, cursor: 'pointer', color: '#ef4444' }}><Trash2 size={14} /></button>
                    </div>
                  </div>
                  {s.last_value && (
                    <div style={{ marginTop: 10, padding: '10px 12px', background: 'var(--bg3)', borderRadius: 8, fontSize: 12, color: 'var(--dim)', lineHeight: 1.7, maxHeight: 90, overflowY: 'auto' }}>
                      {s.last_value}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
