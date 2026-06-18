import { useState, useEffect } from 'react'
import { RefreshCw, Trash2, Plus, Eye, EyeOff, Wifi, WifiOff, Info } from 'lucide-react'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
import api from '../lib/api'

interface Exchange {
  id: number
  exchange_name: string
  api_key: string
  is_primary: boolean
  is_active: boolean
  balance: number
  last_sync: string
  created_at: string
}

const EXCHANGE_OPTIONS = ['Nobitex', 'Binance', 'KuCoin', 'Bybit', 'OKX']

// نوبیتکس فقط توکن می‌خواهد، بقیه کلید + سکرت
const TOKEN_ONLY = ['Nobitex']

const GRADIENT_COLORS = [
  'linear-gradient(135deg, #667eea, #764ba2)',
  'linear-gradient(135deg, #f093fb, #f5576c)',
  'linear-gradient(135deg, #4facfe, #00f2fe)',
  'linear-gradient(135deg, #43e97b, #38f9d7)',
  'linear-gradient(135deg, #fa709a, #fee140)',
  'linear-gradient(135deg, #a18cd1, #fbc2eb)',
]

function getInitials(name: string): string {
  return (name || '??').slice(0, 2).toUpperCase()
}

function formatBalance(n: number): string {
  return (n || 0).toLocaleString('fa-IR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' تومان'
}

function timeAgo(iso: string): string {
  if (!iso) return 'هرگز'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'همین الان'
  if (mins < 60) return `${mins} دقیقه پیش`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} ساعت پیش`
  return `${Math.floor(hrs / 24)} روز پیش`
}

export default function Exchanges() {
  const { t } = useAppStore()

  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState<number | null>(null)
  const [removing, setRemoving] = useState<number | null>(null)

  const [addName, setAddName] = useState('Nobitex')
  const [addKey, setAddKey] = useState('')
  const [addSecret, setAddSecret] = useState('')
  const [showSecret, setShowSecret] = useState(false)
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const isTokenOnly = TOKEN_ONLY.includes(addName)

  const fetchExchanges = () => {
    setLoading(true)
    setError(null)
    api.get('/exchanges/')
      .then(res => setExchanges(res.data))
      .catch(() => setError('بارگذاری صرافی‌ها با خطا مواجه شد'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchExchanges() }, [])

  const handleSync = async (id: number) => {
    setSyncing(id)
    try {
      await api.post(`/exchanges/${id}/sync`)
      await fetchExchanges()
    } catch {}
    setSyncing(null)
  }

  const handleRemove = async (id: number, name: string) => {
    if (!window.confirm(`صرافی ${name} حذف شود؟ این عمل قابل بازگشت نیست.`)) return
    setRemoving(id)
    try {
      await api.delete(`/exchanges/${id}`)
      await fetchExchanges()
    } catch {}
    setRemoving(null)
  }

  const handleAdd = async () => {
    if (!addKey.trim()) {
      setAddError(isTokenOnly ? 'وارد کردن توکن الزامی است' : 'وارد کردن کلید API الزامی است')
      return
    }
    if (!isTokenOnly && !addSecret.trim()) {
      setAddError('وارد کردن کلید و سکرت الزامی است')
      return
    }
    setAddLoading(true)
    setAddError(null)
    try {
      await api.post('/exchanges/', {
        exchange_name: addName,
        api_key: addKey.trim(),
        api_secret: isTokenOnly ? '' : addSecret.trim(),
      })
      setAddKey('')
      setAddSecret('')
      setAddName('Nobitex')
      await fetchExchanges()
    } catch (err: any) {
      setAddError(err?.response?.data?.detail || 'اتصال به صرافی با خطا مواجه شد')
    }
    setAddLoading(false)
  }

  const cardStyle: React.CSSProperties = {
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: 18,
    padding: 24,
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: '10px 14px',
    color: 'var(--text)',
    fontSize: 14,
    outline: 'none',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
  }

  const labelStyle: React.CSSProperties = {
    color: 'var(--faint)',
    fontSize: 12,
    marginBottom: 6,
    fontWeight: 600,
  }

  return (
    <Layout title={t.navExchanges} subtitle="صرافی‌های متصل و افزودن صرافی جدید">
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: 'var(--text)', margin: 0 }}>
          {t.navExchanges}
        </h1>
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--dim)', fontSize: 13 }}>
            <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
            در حال بارگذاری...
          </div>
        )}
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid #ef4444',
          borderRadius: 12,
          padding: '12px 16px',
          color: '#ef4444',
          fontSize: 14,
        }}>
          {error}
        </div>
      )}

      {/* Exchange Grid */}
      {!loading && exchanges.length === 0 ? (
        <div style={{ ...cardStyle, textAlign: 'center', padding: '48px 24px' }}>
          <Plus size={40} style={{ color: 'var(--faint)', marginBottom: 12 }} />
          <div style={{ color: 'var(--dim)', fontSize: 16, fontWeight: 500 }}>هیچ صرافی متصل نیست</div>
          <div style={{ color: 'var(--faint)', fontSize: 13, marginTop: 6 }}>برای شروع، از فرم پایین یک صرافی اضافه کنید</div>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 16,
        }}>
          {exchanges.map((ex, idx) => (
            <div
              key={ex.id}
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: 18,
                padding: 20,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <div style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  background: GRADIENT_COLORS[idx % GRADIENT_COLORS.length],
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontWeight: 800,
                  fontSize: 15,
                  color: '#fff',
                  flexShrink: 0,
                }}>
                  {getInitials(ex.exchange_name)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>
                    {ex.exchange_name}
                  </div>
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    marginTop: 3,
                    padding: '2px 8px',
                    borderRadius: 999,
                    background: `${ex.is_active ? '#22c55e' : '#6b7280'}15`,
                    border: `1px solid ${ex.is_active ? '#22c55e' : '#6b7280'}30`,
                  }}>
                    {ex.is_active
                      ? <Wifi size={11} style={{ color: '#22c55e' }} />
                      : <WifiOff size={11} style={{ color: '#6b7280' }} />
                    }
                    <span style={{ fontSize: 11, fontWeight: 600, color: ex.is_active ? '#22c55e' : '#6b7280' }}>
                      {ex.is_active ? 'متصل' : 'قطع'}
                    </span>
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: 12 }}>
                <div style={{ color: 'var(--faint)', fontSize: 11, marginBottom: 4, fontWeight: 600 }}>موجودی</div>
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>
                  {formatBalance(ex.balance ?? 0)}
                </div>
              </div>

              <div style={{ color: 'var(--faint)', fontSize: 12, marginBottom: 16 }}>
                آخرین همگام‌سازی: {timeAgo(ex.last_sync)}
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => handleSync(ex.id)}
                  disabled={syncing === ex.id}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                    padding: '8px 12px',
                    borderRadius: 10,
                    border: '1px solid var(--border)',
                    background: 'var(--bg2)',
                    color: 'var(--dim)',
                    fontSize: 13,
                    fontWeight: 600,
                    fontFamily: 'inherit',
                    cursor: syncing === ex.id ? 'not-allowed' : 'pointer',
                    opacity: syncing === ex.id ? 0.6 : 1,
                    transition: 'all 0.15s',
                  }}
                >
                  <RefreshCw size={13} style={{ animation: syncing === ex.id ? 'spin 1s linear infinite' : 'none' }} />
                  همگام‌سازی
                </button>
                <button
                  onClick={() => handleRemove(ex.id, ex.exchange_name)}
                  disabled={removing === ex.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                    padding: '8px 14px',
                    borderRadius: 10,
                    border: '1px solid rgba(239,68,68,0.3)',
                    background: 'rgba(239,68,68,0.06)',
                    color: '#ef4444',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: removing === ex.id ? 'not-allowed' : 'pointer',
                    opacity: removing === ex.id ? 0.6 : 1,
                    transition: 'all 0.15s',
                  }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Exchange */}
      <div style={cardStyle}>
        <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 700, color: 'var(--text)', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Plus size={18} style={{ color: 'var(--accent)' }} />
          افزودن صرافی
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <div style={labelStyle}>صرافی</div>
            <select
              value={addName}
              onChange={e => setAddName(e.target.value)}
              style={{ ...inputStyle, cursor: 'pointer' }}
            >
              {EXCHANGE_OPTIONS.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>

          {/* راهنمای نوبیتکس */}
          {isTokenOnly && (
            <div style={{
              display: 'flex',
              gap: 10,
              background: 'rgba(75,224,255,0.06)',
              border: '1px solid rgba(75,224,255,0.2)',
              borderRadius: 10,
              padding: '12px 14px',
            }}>
              <Info size={16} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: 12.5, color: 'var(--dim)', lineHeight: 1.7 }}>
                برای دریافت توکن نوبیتکس وارد حساب نوبیتکس خود شوید، به بخش
                {' '}<b style={{ color: 'var(--text)' }}>تنظیمات ← API</b>{' '}
                بروید و یک توکن جدید بسازید. سپس توکن را در کادر زیر وارد کنید.
              </div>
            </div>
          )}

          <div>
            <div style={labelStyle}>{isTokenOnly ? 'توکن API نوبیتکس' : 'کلید API'}</div>
            <input
              type="text"
              value={addKey}
              onChange={e => setAddKey(e.target.value)}
              placeholder={isTokenOnly ? 'توکن دریافتی از نوبیتکس را وارد کنید' : 'کلید API را وارد کنید'}
              style={inputStyle}
              dir="ltr"
            />
          </div>

          {!isTokenOnly && (
            <div>
              <div style={labelStyle}>سکرت API</div>
              <div style={{ position: 'relative' }}>
                <input
                  type={showSecret ? 'text' : 'password'}
                  value={addSecret}
                  onChange={e => setAddSecret(e.target.value)}
                  placeholder="سکرت API را وارد کنید"
                  style={{ ...inputStyle, paddingInlineEnd: 44 }}
                  dir="ltr"
                />
                <button
                  onClick={() => setShowSecret(s => !s)}
                  style={{
                    position: 'absolute',
                    top: '50%',
                    insetInlineEnd: 12,
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--dim)',
                    display: 'flex',
                    alignItems: 'center',
                    padding: 0,
                  }}
                >
                  {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          )}

          {addError && (
            <div style={{
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 10,
              padding: '10px 14px',
              color: '#ef4444',
              fontSize: 13,
            }}>
              {addError}
            </div>
          )}

          <button
            onClick={handleAdd}
            disabled={addLoading}
            style={{
              width: '100%',
              background: 'var(--accent)',
              color: '#05121a',
              border: 'none',
              borderRadius: 12,
              padding: '13px 24px',
              fontSize: 15,
              fontWeight: 700,
              fontFamily: 'inherit',
              cursor: addLoading ? 'not-allowed' : 'pointer',
              opacity: addLoading ? 0.7 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              transition: 'opacity 0.2s',
              marginTop: 4,
            }}
          >
            {addLoading ? (
              <>
                <RefreshCw size={15} style={{ animation: 'spin 1s linear infinite' }} />
                در حال اتصال...
              </>
            ) : (
              <>
                <Plus size={15} />
                اتصال صرافی
              </>
            )}
          </button>
        </div>
      </div>
    </div>
    </Layout>
  )
}
