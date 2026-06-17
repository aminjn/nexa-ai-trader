import { useState, useEffect } from 'react'
import { AlertTriangle, TrendingDown, BarChart3, Layers, Save, Percent, Activity } from 'lucide-react'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
import api from '../lib/api'

const PAIRS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'MATIC/USDT'] as const
type Pair = (typeof PAIRS)[number]

interface ShortSettings {
  short_enabled: boolean
  leverage: number
  short_pairs: Pair[]
}

interface ShortStats {
  open_positions: number
  total_pnl: number
  win_rate: number
}

const DEFAULT_SETTINGS: ShortSettings = {
  short_enabled: false,
  leverage: 5,
  short_pairs: ['BTC/USDT', 'ETH/USDT'],
}

const DEFAULT_STATS: ShortStats = { open_positions: 0, total_pnl: 0, win_rate: 0 }

export default function Short() {
  const { t } = useAppStore()

  const [settings, setSettings] = useState<ShortSettings>(DEFAULT_SETTINGS)
  const [stats, setStats] = useState<ShortStats>(DEFAULT_STATS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.get('/strategy/'),
      api.get('/strategy/short-stats').catch(() => ({ data: DEFAULT_STATS })),
    ])
      .then(([stratRes, statsRes]) => {
        const d = stratRes.data
        setSettings(prev => ({
          ...prev,
          short_enabled: d.short_enabled ?? prev.short_enabled,
          leverage: d.leverage ?? prev.leverage,
          short_pairs: (d.short_pairs as Pair[] | undefined) ?? prev.short_pairs,
        }))
        setStats(statsRes.data as ShortStats)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const togglePair = (pair: Pair) => {
    if (!settings.short_enabled) return
    setSettings(prev => ({
      ...prev,
      short_pairs: prev.short_pairs.includes(pair)
        ? prev.short_pairs.filter(p => p !== pair)
        : [...prev.short_pairs, pair],
    }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/strategy/', {
        short_enabled: settings.short_enabled,
        leverage: settings.leverage,
        short_pairs: settings.short_pairs,
      })
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch {}
    setSaving(false)
  }

  const leverageColor =
    settings.leverage <= 5 ? '#22c55e' :
    settings.leverage <= 10 ? '#f59e0b' : '#ef4444'

  const leverageLabel =
    settings.leverage <= 5 ? 'ریسک پایین' :
    settings.leverage <= 10 ? 'ریسک متوسط' : 'ریسک بالا'

  const pnlColor = stats.total_pnl >= 0 ? '#22c55e' : '#ef4444'

  const bufferPct = Math.max(5, 100 - settings.leverage * 4.5)
  const bufferColor =
    bufferPct >= 60 ? '#22c55e' :
    bufferPct >= 30 ? '#f59e0b' : '#ef4444'
  const bufferLabel =
    bufferPct >= 60 ? 'امن' :
    bufferPct >= 30 ? 'هشدار' : 'خطر'

  const cardStyle: React.CSSProperties = {
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: 18,
    padding: 24,
  }

  return (
    <Layout title={t.navShort} subtitle="تنظیمات معاملات فروش (شورت)">
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: 'var(--text)', margin: 0 }}>
          {t.navShort}
        </h1>
      </div>

      {loading ? (
        <div style={{ color: 'var(--dim)', textAlign: 'center', padding: 40 }}>در حال بارگذاری...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>

          {/* Left Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* Short Trading Toggle */}
            <div style={{
              ...cardStyle,
              border: `1px solid ${settings.short_enabled ? 'var(--accent)' : 'var(--border)'}`,
              transition: 'border-color 0.2s',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <TrendingDown size={18} style={{ color: 'var(--accent)' }} />
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>
                  معاملات فروش (شورت)
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
                    فعال‌سازی معاملات شورت
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--dim)' }}>
                    {settings.short_enabled
                      ? 'معاملات شورت فعال است'
                      : 'برای معامله در بازارهای نزولی فعال کنید'}
                  </div>
                </div>
                <div
                  onClick={() => setSettings(p => ({ ...p, short_enabled: !p.short_enabled }))}
                  style={{
                    width: 52,
                    height: 28,
                    borderRadius: 14,
                    background: settings.short_enabled ? 'var(--accent)' : 'var(--bg3)',
                    position: 'relative',
                    cursor: 'pointer',
                    transition: 'background 0.3s',
                    flexShrink: 0,
                    marginInlineStart: 16,
                  }}
                >
                  <div style={{
                    position: 'absolute',
                    top: 4,
                    insetInlineStart: settings.short_enabled ? 28 : 4,
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    background: 'white',
                    transition: 'inset-inline-start 0.3s',
                    boxShadow: '0 1px 4px rgba(0,0,0,0.25)',
                  }} />
                </div>
              </div>
            </div>

            {/* Warning */}
            <div style={{
              background: 'rgba(251,191,36,0.08)',
              border: '1px solid var(--amber, #f59e0b)',
              borderRadius: 14,
              padding: 20,
              display: 'flex',
              gap: 14,
              alignItems: 'flex-start',
            }}>
              <AlertTriangle size={20} style={{ color: 'var(--amber, #f59e0b)', flexShrink: 0, marginTop: 2 }} />
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--amber, #f59e0b)', marginBottom: 6, fontFamily: "'Space Grotesk', sans-serif" }}>
                  هشدار ریسک
                </div>
                <div style={{ fontSize: 13, color: 'var(--dim)', lineHeight: 1.6 }}>
                  معاملات شورت ریسک بالایی دارد. ممکن است بیش از سرمایه اولیه خود ضرر کنید.
                  پوزیشن‌های اهرم‌دار می‌توانند در شرایط پرنوسان بازار به سرعت لیکویید شوند.
                </div>
              </div>
            </div>

            {/* Leverage */}
            <div style={{ ...cardStyle, opacity: settings.short_enabled ? 1 : 0.4, transition: 'opacity 0.2s' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                <BarChart3 size={18} style={{ color: 'var(--accent)' }} />
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>
                  اهرم
                </span>
              </div>
              <div style={{ textAlign: 'center', marginBottom: 20 }}>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 64,
                  fontWeight: 900,
                  color: leverageColor,
                  letterSpacing: '-3px',
                  lineHeight: 1,
                }}>
                  {settings.leverage}x
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={20}
                step={1}
                value={settings.leverage}
                disabled={!settings.short_enabled}
                onChange={e => setSettings(p => ({ ...p, leverage: parseInt(e.target.value) }))}
                style={{
                  width: '100%',
                  marginBottom: 6,
                  cursor: settings.short_enabled ? 'pointer' : 'not-allowed',
                  accentColor: leverageColor,
                }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--faint)', fontFamily: "'JetBrains Mono', monospace", marginBottom: 14 }}>
                <span>1x</span>
                <span>20x</span>
              </div>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 14px',
                borderRadius: 999,
                background: `${leverageColor}18`,
                border: `1px solid ${leverageColor}44`,
                fontSize: 12,
                fontWeight: 700,
                color: leverageColor,
              }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: leverageColor, display: 'inline-block' }} />
                {leverageLabel}
              </div>
            </div>

            {/* Short Pairs */}
            <div style={{ ...cardStyle, opacity: settings.short_enabled ? 1 : 0.4, transition: 'opacity 0.2s' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                <Layers size={18} style={{ color: 'var(--accent)' }} />
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>
                  جفت‌ارزهای شورت
                </span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                {PAIRS.map(pair => {
                  const selected = settings.short_pairs.includes(pair)
                  return (
                    <button
                      key={pair}
                      onClick={() => togglePair(pair)}
                      disabled={!settings.short_enabled}
                      style={{
                        padding: '8px 16px',
                        borderRadius: 999,
                        border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
                        background: selected ? 'rgba(75,224,255,0.12)' : 'var(--bg2)',
                        color: selected ? 'var(--accent)' : 'var(--dim)',
                        fontSize: 13,
                        fontWeight: 600,
                        fontFamily: "'JetBrains Mono', monospace",
                        cursor: settings.short_enabled ? 'pointer' : 'not-allowed',
                        transition: 'all 0.15s',
                      }}
                    >
                      {pair}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* Short Statistics */}
            <div style={cardStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
                <Activity size={18} style={{ color: 'var(--accent)' }} />
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>
                  آمار معاملات شورت
                </span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {[
                  { label: 'پوزیشن‌های باز', value: String(stats.open_positions), color: 'var(--text)', icon: <Layers size={15} /> },
                  {
                    label: 'سود/زیان کل',
                    value: `${stats.total_pnl >= 0 ? '+' : ''}$${stats.total_pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                    color: pnlColor,
                    icon: <TrendingDown size={15} />,
                  },
                  { label: 'نرخ موفقیت', value: `${stats.win_rate.toFixed(1)}%`, color: stats.win_rate >= 50 ? '#22c55e' : '#ef4444', icon: <Percent size={15} /> },
                ].map(({ label, value, color, icon }, i, arr) => (
                  <div
                    key={label}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '16px 0',
                      borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--dim)' }}>
                      {icon}
                      <span style={{ fontSize: 14 }}>{label}</span>
                    </div>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 18, fontWeight: 700, color }}>
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Liquidation Buffer */}
            <div style={cardStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <BarChart3 size={18} style={{ color: 'var(--accent)' }} />
                <span style={{ fontFamily: "'Space Grotesk', sans-serif", fontWeight: 700, fontSize: 16, color: 'var(--text)' }}>
                  حاشیه امنیت لیکویید
                </span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--faint)', marginBottom: 24 }}>امنیت مارجین</div>

              <div style={{
                position: 'relative',
                height: 18,
                borderRadius: 999,
                overflow: 'hidden',
                display: 'flex',
                marginBottom: 12,
                background: 'var(--bg3)',
              }}>
                <div style={{ width: '40%', background: '#22c55e', opacity: 0.7 }} />
                <div style={{ width: '30%', background: '#f59e0b', opacity: 0.7 }} />
                <div style={{ width: '30%', background: '#ef4444', opacity: 0.7 }} />
                <div style={{
                  position: 'absolute',
                  top: 0,
                  bottom: 0,
                  insetInlineStart: `${Math.min(bufferPct, 98)}%`,
                  width: 3,
                  background: '#fff',
                  boxShadow: '0 0 6px rgba(255,255,255,0.8)',
                  borderRadius: 2,
                  transform: 'translateX(-50%)',
                }} />
              </div>

              <div style={{ display: 'flex', fontSize: 11, fontFamily: "'JetBrains Mono', monospace", marginBottom: 20 }}>
                <div style={{ width: '40%', color: '#22c55e' }}>امن</div>
                <div style={{ width: '30%', color: '#f59e0b', textAlign: 'center' }}>هشدار</div>
                <div style={{ width: '30%', color: '#ef4444', textAlign: 'end' }}>خطر</div>
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '14px 16px',
                borderRadius: 12,
                background: `${bufferColor}10`,
                border: `1px solid ${bufferColor}35`,
              }}>
                <div style={{ fontSize: 13, color: 'var(--dim)' }}>حاشیه فعلی</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 20, fontWeight: 700, color: bufferColor }}>
                    {bufferPct.toFixed(1)}%
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: bufferColor, padding: '3px 8px', borderRadius: 999, background: `${bufferColor}20` }}>
                    {bufferLabel}
                  </span>
                </div>
              </div>
            </div>

            {/* Save */}
            <div>
              {success && (
                <div style={{
                  background: 'rgba(34,197,94,0.12)',
                  border: '1px solid #22c55e',
                  borderRadius: 10,
                  padding: '10px 16px',
                  color: '#22c55e',
                  fontSize: 14,
                  textAlign: 'center',
                  marginBottom: 12,
                }}>
                  تنظیمات ذخیره شد!
                </div>
              )}
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  width: '100%',
                  background: 'var(--accent)',
                  color: '#05121a',
                  border: 'none',
                  borderRadius: 12,
                  padding: '14px 24px',
                  fontSize: 15,
                  fontWeight: 700,
                  cursor: saving ? 'not-allowed' : 'pointer',
                  opacity: saving ? 0.7 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  transition: 'opacity 0.2s',
                }}
              >
                <Save size={16} />
                {saving ? 'در حال ذخیره...' : 'ذخیره تنظیمات شورت'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </Layout>
  )
}
