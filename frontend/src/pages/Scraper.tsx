import { useState, useEffect } from 'react'
import { Globe, Plus, Trash2, Play, Eye, RefreshCw } from 'lucide-react'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
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

  const load = async () => {
    try { const r = await api.get('/scraper/sources'); setSources(r.data || []) }
    catch {} finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const testScrape = async () => {
    if (!url.trim()) { toast.error('آدرس سایت را وارد کنید'); return }
    setTesting(true); setPreview('')
    try {
      const r = await api.post('/scraper/test', { url: url.trim(), selector: selector.trim(), use_proxy: useProxy })
      setPreview(r.data.preview || '')
    } catch (e: any) { toast.error(e.response?.data?.detail || 'خطا در تست') }
    finally { setTesting(false) }
  }

  const addSource = async () => {
    if (!name.trim() || !url.trim()) { toast.error('نام و آدرس الزامی است'); return }
    setAdding(true)
    try {
      await api.post('/scraper/sources', { name: name.trim(), url: url.trim(), selector: selector.trim(), use_proxy: useProxy })
      toast.success('منبع اضافه شد')
      setName(''); setUrl(''); setSelector(''); setUseProxy(false); setPreview('')
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
          <div style={{ marginTop: 14 }}>
            <div style={label}>CSS Selector فیلد موردنظر (اختیاری)</div>
            <input style={inputStyle} value={selector} onChange={e => setSelector(e.target.value)} placeholder="مثلاً .news-title یا h2 یا .price" dir="ltr" />
            <div style={{ fontSize: 11, color: 'var(--faint)', marginTop: 6, lineHeight: 1.7 }}>
              با CSS selector انتخاب می‌کنی کدام بخش سایت خوانده شود. خالی بگذاری = کل متن صفحه. (مثال: عنوان اخبار <code>h2 a</code>، قیمت <code>.price</code>)
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 14, flexWrap: 'wrap' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 14 }}>
              <input type="checkbox" checked={useProxy} onChange={e => setUseProxy(e.target.checked)} />
              سایت خارجی است (از پروکسی استفاده کن)
            </label>
          </div>

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
