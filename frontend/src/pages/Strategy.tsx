import { useState, useEffect } from 'react'
import { Save, TrendingUp, Shield, Activity, Zap } from 'lucide-react'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
import api from '../lib/api'

type MarketType = 'spot' | 'futures'
type RiskLevel = 'Conservative' | 'Balanced' | 'Aggressive'

export default function Strategy() {
  const { t } = useAppStore()

  const [marketType, setMarketType] = useState<MarketType>('spot')
  const [targetProfit, setTargetProfit] = useState(3)
  const [tradesPerDay, setTradesPerDay] = useState(40)
  const [capitalPct, setCapitalPct] = useState(50)
  const [stopLoss, setStopLoss] = useState(2)
  const [saving, setSaving] = useState(false)
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/strategy/')
      .then(res => {
        const d = res.data
        if (d.market_type) setMarketType(d.market_type)
        if (d.target_profit != null) setTargetProfit(d.target_profit)
        if (d.trades_per_day != null) setTradesPerDay(d.trades_per_day)
        if (d.capital_pct != null) setCapitalPct(d.capital_pct)
        if (d.stop_loss != null) setStopLoss(d.stop_loss)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const estimatedDaily = (targetProfit * tradesPerDay / 100).toFixed(2)

  const riskLevel: RiskLevel =
    targetProfit < 2 ? 'Conservative' :
    targetProfit > 5 ? 'Aggressive' : 'Balanced'

  const riskMeta: Record<RiskLevel, { icon: React.ReactNode; label: string; desc: string; color: string }> = {
    Conservative: { icon: <Shield size={16} />, label: 'محافظه‌کارانه', desc: 'ریسک پایین، بازده پایدار', color: '#22c55e' },
    Balanced:     { icon: <Activity size={16} />, label: 'متعادل', desc: 'ریسک و بازده متوسط', color: 'var(--accent)' },
    Aggressive:   { icon: <Zap size={16} />, label: 'تهاجمی', desc: 'ریسک بالا، بازده بالا', color: '#ef4444' },
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/strategy/', {
        market_type: marketType,
        target_profit: targetProfit,
        trades_per_day: tradesPerDay,
        capital_pct: capitalPct,
        stop_loss: stopLoss,
      })
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch {}
    setSaving(false)
  }

  const cardStyle: React.CSSProperties = {
    background: 'var(--panel)',
    border: '1px solid var(--border)',
    borderRadius: 18,
    padding: 24,
  }

  const sliderRow = (
    label: string,
    value: number,
    min: number,
    max: number,
    step: number,
    suffix: string,
    setter: (v: number) => void
  ) => (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ color: 'var(--dim)', fontSize: 13 }}>{label}</span>
        <span style={{ color: 'var(--accent)', fontFamily: "'JetBrains Mono', monospace", fontSize: 14, fontWeight: 600 }}>
          {value}{suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={e => setter(Number(e.target.value))}
        style={{ width: '100%', accentColor: 'var(--accent)', height: 6, cursor: 'pointer' }}
      />
    </div>
  )

  return (
    <Layout title={t.navStrategy} subtitle="تنظیم استراتژی و پارامترهای معاملاتی">
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 24, fontWeight: 700, color: 'var(--text)', margin: 0 }}>
          {t.navStrategy}
        </h1>
      </div>

      {loading ? (
        <div style={{ color: 'var(--dim)', textAlign: 'center', padding: 40 }}>در حال بارگذاری...</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>

          {/* Left Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* Market Settings */}
            <div style={cardStyle}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 16 }}>
                تنظیمات بازار
              </div>
              <div style={{ color: 'var(--faint)', fontSize: 12, marginBottom: 10, letterSpacing: '0.08em' }}>
                نوع بازار
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                {(['spot', 'futures'] as const).map(type => (
                  <button
                    key={type}
                    onClick={() => setMarketType(type)}
                    style={{
                      borderRadius: 12,
                      padding: '10px 24px',
                      fontWeight: 600,
                      fontSize: 14,
                      cursor: 'pointer',
                      border: marketType === type ? 'none' : '1px solid var(--border)',
                      background: marketType === type ? 'var(--accent)' : 'var(--bg2)',
                      color: marketType === type ? '#05121a' : 'var(--text)',
                      transition: 'all 0.2s',
                    }}
                  >
                    {type === 'spot' ? 'اسپات' : 'فیوچرز'}
                  </button>
                ))}
              </div>
            </div>

            {/* Trading Parameters */}
            <div style={cardStyle}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 20 }}>
                پارامترهای معاملاتی
              </div>
              {sliderRow('سود هدف هر معامله', targetProfit, 1, 8, 0.5, '%', setTargetProfit)}
              {sliderRow('تعداد معاملات روزانه', tradesPerDay, 10, 120, 5, '', setTradesPerDay)}
              {sliderRow('درصد سرمایه فعال', capitalPct, 10, 100, 5, '%', setCapitalPct)}
              {sliderRow('حد ضرر', stopLoss, 0.5, 6, 0.5, '%', setStopLoss)}
            </div>
          </div>

          {/* Right Column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* Daily Projection */}
            <div style={cardStyle}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
                <TrendingUp size={18} style={{ color: 'var(--accent)' }} />
                پیش‌بینی روزانه
              </div>
              <div style={{ textAlign: 'center', padding: '24px 0' }}>
                <div style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 52,
                  fontWeight: 700,
                  color: '#22c55e',
                  lineHeight: 1,
                  marginBottom: 12,
                }}>
                  +{estimatedDaily}%
                </div>
                <div style={{ color: 'var(--dim)', fontSize: 14 }}>سود روزانه تخمینی</div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 8 }}>
                <div style={{ background: 'var(--bg2)', borderRadius: 10, padding: '12px 16px' }}>
                  <div style={{ color: 'var(--faint)', fontSize: 11, marginBottom: 4 }}>معاملات روزانه</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text)', fontWeight: 600 }}>{tradesPerDay}</div>
                </div>
                <div style={{ background: 'var(--bg2)', borderRadius: 10, padding: '12px 16px' }}>
                  <div style={{ color: 'var(--faint)', fontSize: 11, marginBottom: 4 }}>سرمایه استفاده‌شده</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--text)', fontWeight: 600 }}>{capitalPct}%</div>
                </div>
              </div>
            </div>

            {/* Risk Level */}
            <div style={cardStyle}>
              <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16, fontWeight: 600, color: 'var(--text)', marginBottom: 16 }}>
                سطح ریسک
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                {(['Conservative', 'Balanced', 'Aggressive'] as const).map(level => {
                  const meta = riskMeta[level]
                  const isActive = riskLevel === level
                  return (
                    <div
                      key={level}
                      style={{
                        flex: 1,
                        borderRadius: 12,
                        padding: '14px 10px',
                        textAlign: 'center',
                        border: isActive ? `1px solid ${meta.color}` : '1px solid var(--border)',
                        background: isActive ? `${meta.color}1a` : 'var(--bg2)',
                        transition: 'all 0.3s',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 6, color: isActive ? meta.color : 'var(--faint)' }}>
                        {meta.icon}
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: isActive ? meta.color : 'var(--dim)', marginBottom: 4 }}>{meta.label}</div>
                      <div style={{ fontSize: 11, color: 'var(--faint)' }}>{meta.desc}</div>
                    </div>
                  )
                })}
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
                {saving ? 'در حال ذخیره...' : 'ذخیره تنظیمات'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </Layout>
  )
}
