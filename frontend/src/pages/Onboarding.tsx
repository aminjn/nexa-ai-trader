import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Eye, EyeOff, ArrowRight, ArrowLeft, Rocket } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import api from '../lib/api';
import Logo from '../components/Logo';

const EXCHANGES = ['Nobitex', 'Binance', 'KuCoin', 'Other'];

const STEPS = ['خوش‌آمد', 'اتصال صرافی', 'استراتژی', 'خلاصه'];

export default function Onboarding() {
  const navigate = useNavigate();
  const { dir } = useAppStore();

  const [step, setStep] = useState(0);
  const [exchange, setExchange] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [marketType, setMarketType] = useState<'spot' | 'futures'>('spot');
  const [targetProfit, setTargetProfit] = useState(3);
  const [tradesPerDay, setTradesPerDay] = useState(40);
  const [capitalPct, setCapitalPct] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleNext = async () => {
    setError('');

    if (step === 1 && exchange && apiKey) {
      setLoading(true);
      try {
        await api.post('/exchanges/', {
          exchange_name: exchange.toLowerCase(),
          api_key: apiKey,
          api_secret: apiSecret,
        });
      } catch (err: any) {
        setError(err?.response?.data?.detail || 'اتصال به صرافی با خطا مواجه شد');
        setLoading(false);
        return;
      } finally {
        setLoading(false);
      }
    }

    if (step === 2) {
      try {
        await api.put('/strategy/', {
          market_type: marketType,
          target_profit: targetProfit,
          trades_per_day: tradesPerDay,
          capital_pct: capitalPct,
        });
      } catch {
        // non-blocking
      }
    }

    if (step === 3) {
      navigate('/dashboard');
      return;
    }

    setStep((s) => s + 1);
  };

  const handleSkip = () => {
    setStep((s) => s + 1);
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '12px 16px',
    background: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '10px',
    color: 'var(--text)',
    fontSize: '14px',
    fontFamily: 'JetBrains Mono, monospace',
    outline: 'none',
    boxSizing: 'border-box',
    transition: 'border-color 0.2s',
  };

  const labelStyle: React.CSSProperties = {
    display: 'block',
    fontSize: '12px',
    color: 'var(--faint)',
    marginBlockEnd: '6px',
    fontFamily: 'Space Grotesk, sans-serif',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 24px',
      background: 'var(--bg)',
      direction: dir,
      fontFamily: 'Space Grotesk, sans-serif',
    }}>
      {/* Background grid */}
      <div style={{
        position: 'fixed',
        inset: 0,
        backgroundImage: 'linear-gradient(var(--grid, rgba(255,255,255,0.03)) 1px, transparent 1px), linear-gradient(90deg, var(--grid, rgba(255,255,255,0.03)) 1px, transparent 1px)',
        backgroundSize: '48px 48px',
        pointerEvents: 'none',
        zIndex: 0,
      }} />

      <div style={{
        position: 'relative',
        zIndex: 1,
        width: '100%',
        maxWidth: '640px',
        background: 'var(--panel)',
        border: '1px solid var(--border)',
        borderRadius: '18px',
        padding: '40px',
        boxShadow: '0 40px 100px -40px rgba(0,0,0,0.6)',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBlockEnd: '32px' }}>
          <Logo size={42} />
          <span style={{
            fontFamily: 'Space Grotesk, sans-serif',
            fontWeight: 700,
            fontSize: '18px',
            color: 'var(--text)',
            marginBlockStart: '10px',
          }}>
            NEXA AI Trader
          </span>
        </div>

        {/* Step indicator */}
        <div style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBlockEnd: '36px' }}>
          {/* Track line */}
          <div style={{
            position: 'absolute',
            insetBlockStart: '16px',
            insetInlineStart: '16px',
            insetInlineEnd: '16px',
            height: '2px',
            background: 'var(--border)',
            zIndex: 0,
          }} />
          {/* Progress fill */}
          <div style={{
            position: 'absolute',
            insetBlockStart: '16px',
            insetInlineStart: '16px',
            height: '2px',
            width: `${(step / (STEPS.length - 1)) * 100}%`,
            background: 'var(--accent)',
            zIndex: 0,
            transition: 'width 0.35s ease',
          }} />

          {STEPS.map((label, i) => {
            const completed = i < step;
            const active = i === step;
            return (
              <div key={i} style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontFamily: 'JetBrains Mono, monospace',
                  fontWeight: 700,
                  fontSize: '13px',
                  background: completed ? '#00c864' : active ? 'var(--accent)' : 'var(--bg2)',
                  color: completed || active ? '#05121a' : 'var(--dim)',
                  border: completed ? '2px solid #00c864' : active ? '2px solid var(--accent)' : '2px solid var(--border)',
                  transition: 'all 0.25s',
                  boxShadow: active ? '0 0 12px var(--accent)' : 'none',
                }}>
                  {completed ? <Check size={14} /> : i + 1}
                </div>
                <span style={{
                  fontSize: '11px',
                  color: active ? 'var(--accent)' : completed ? '#00c864' : 'var(--dim)',
                  fontWeight: active ? 600 : 400,
                  whiteSpace: 'nowrap',
                  transition: 'color 0.25s',
                }}>
                  {label}
                </span>
              </div>
            );
          })}
        </div>

        {/* ── Step 0: Welcome ── */}
        {step === 0 && (
          <div style={{ textAlign: 'center', padding: '16px 0 8px' }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              background: 'rgba(0,200,100,0.1)',
              border: '1px solid rgba(0,200,100,0.25)',
              borderRadius: '20px',
              padding: '6px 14px',
              marginBlockEnd: '24px',
            }}>
              <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#00c864', display: 'inline-block' }} />
              <span style={{ fontSize: '13px', color: '#00c864', fontFamily: 'JetBrains Mono, monospace', fontWeight: 500 }}>
                سیستم آماده
              </span>
            </div>

            <h2 style={{
              fontSize: '30px',
              fontWeight: 800,
              color: 'var(--text)',
              fontFamily: 'Space Grotesk, sans-serif',
              letterSpacing: '-0.03em',
              marginBlockStart: 0,
              marginBlockEnd: '14px',
            }}>
              به نکسا خوش آمدید
            </h2>

            <p style={{
              fontSize: '15px',
              color: 'var(--dim)',
              lineHeight: 1.7,
              maxWidth: '44ch',
              marginInline: 'auto',
              marginBlockEnd: 0,
            }}>
              سیستم معاملاتی هوشمند شما آماده است. در چند گام آن را راه‌اندازی کنید.
            </p>
          </div>
        )}

        {/* ── Step 1: Connect Exchange ── */}
        {step === 1 && (
          <div>
            <h2 style={{
              fontSize: '22px',
              fontWeight: 700,
              color: 'var(--text)',
              fontFamily: 'Space Grotesk, sans-serif',
              marginBlockStart: 0,
              marginBlockEnd: '8px',
            }}>
              اتصال صرافی
            </h2>
            <p style={{ fontSize: '14px', color: 'var(--dim)', lineHeight: 1.7, marginBlockStart: 0, marginBlockEnd: '20px' }}>
              صرافی خود را انتخاب کنید و اطلاعات API را برای شروع معامله وارد کنید.
            </p>

            {/* Exchange grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '10px',
              marginBlockEnd: '20px',
            }}>
              {EXCHANGES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setExchange(ex)}
                  style={{
                    padding: '14px',
                    border: exchange === ex ? '1px solid var(--accent)' : '1px solid var(--border)',
                    borderRadius: '12px',
                    background: exchange === ex ? 'rgba(0,229,255,0.1)' : 'var(--bg2)',
                    color: exchange === ex ? 'var(--accent)' : 'var(--dim)',
                    fontFamily: 'JetBrains Mono, monospace',
                    fontWeight: 600,
                    fontSize: '14px',
                    cursor: 'pointer',
                    transition: 'all 0.18s',
                    boxShadow: exchange === ex ? '0 0 12px rgba(0,229,255,0.15)' : 'none',
                  }}
                >
                  {ex}
                </button>
              ))}
            </div>

            {/* API credentials */}
            {exchange && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <label style={labelStyle}>کلید API</label>
                  <input
                    type="text"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="کلید API خود را اینجا وارد کنید"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>رمز API</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showSecret ? 'text' : 'password'}
                      value={apiSecret}
                      onChange={(e) => setApiSecret(e.target.value)}
                      placeholder="رمز API خود را اینجا وارد کنید"
                      style={{ ...inputStyle, paddingInlineEnd: '44px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowSecret(!showSecret)}
                      style={{
                        position: 'absolute',
                        insetBlockStart: '50%',
                        insetInlineEnd: '12px',
                        transform: 'translateY(-50%)',
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--dim)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        padding: 0,
                      }}
                    >
                      {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div style={{
                marginBlockStart: '14px',
                padding: '10px 14px',
                background: 'rgba(255,60,60,0.1)',
                border: '1px solid rgba(255,60,60,0.3)',
                borderRadius: '8px',
                color: '#ff6060',
                fontSize: '13px',
              }}>
                {error}
              </div>
            )}
          </div>
        )}

        {/* ── Step 2: Strategy ── */}
        {step === 2 && (
          <div>
            <h2 style={{
              fontSize: '22px',
              fontWeight: 700,
              color: 'var(--text)',
              fontFamily: 'Space Grotesk, sans-serif',
              marginBlockStart: 0,
              marginBlockEnd: '8px',
            }}>
              تنظیم استراتژی
            </h2>
            <p style={{ fontSize: '14px', color: 'var(--dim)', lineHeight: 1.7, marginBlockStart: 0, marginBlockEnd: '24px' }}>
              تنظیمات معاملاتی خود را مشخص کنید. هر زمان می‌توانید آن‌ها را از داشبورد تغییر دهید.
            </p>

            {/* Spot / Futures toggle */}
            <div style={{
              display: 'flex',
              background: 'var(--bg2)',
              border: '1px solid var(--border)',
              borderRadius: '10px',
              padding: '4px',
              marginBlockEnd: '28px',
            }}>
              {(['spot', 'futures'] as const).map((mt) => (
                <button
                  key={mt}
                  onClick={() => setMarketType(mt)}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: '7px',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: 600,
                    fontFamily: 'Space Grotesk, sans-serif',
                    background: marketType === mt ? 'var(--accent)' : 'transparent',
                    color: marketType === mt ? '#05121a' : 'var(--dim)',
                    transition: 'all 0.2s',
                  }}
                >
                  {mt === 'spot' ? 'اسپات' : 'فیوچرز'}
                </button>
              ))}
            </div>

            {/* Sliders */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Target Profit */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBlockEnd: '10px' }}>
                  <span style={{ fontSize: '14px', color: 'var(--text)', fontWeight: 500 }}>سود هدف</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)', fontWeight: 700, fontSize: '15px' }}>
                    {targetProfit}%
                  </span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={8}
                  step={0.5}
                  value={targetProfit}
                  onChange={(e) => setTargetProfit(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBlockStart: '4px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--faint)' }}>1%</span>
                  <span style={{ fontSize: '11px', color: 'var(--faint)' }}>8%</span>
                </div>
              </div>

              {/* Trades per day */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBlockEnd: '10px' }}>
                  <span style={{ fontSize: '14px', color: 'var(--text)', fontWeight: 500 }}>معاملات در روز</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)', fontWeight: 700, fontSize: '15px' }}>
                    {tradesPerDay}×
                  </span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={120}
                  step={5}
                  value={tradesPerDay}
                  onChange={(e) => setTradesPerDay(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBlockStart: '4px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--faint)' }}>10×</span>
                  <span style={{ fontSize: '11px', color: 'var(--faint)' }}>120×</span>
                </div>
              </div>

              {/* Capital percentage */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBlockEnd: '10px' }}>
                  <span style={{ fontSize: '14px', color: 'var(--text)', fontWeight: 500 }}>سرمایه درگیر</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--accent)', fontWeight: 700, fontSize: '15px' }}>
                    {capitalPct}%
                  </span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={100}
                  step={5}
                  value={capitalPct}
                  onChange={(e) => setCapitalPct(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBlockStart: '4px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--faint)' }}>10%</span>
                  <span style={{ fontSize: '11px', color: 'var(--faint)' }}>100%</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Step 3: Summary & Launch ── */}
        {step === 3 && (
          <div>
            <div style={{ textAlign: 'center', marginBlockEnd: '28px' }}>
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: 'rgba(0,229,255,0.12)',
                border: '2px solid var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginInline: 'auto',
                marginBlockEnd: '16px',
                boxShadow: '0 0 24px rgba(0,229,255,0.25)',
              }}>
                <Rocket size={26} color="var(--accent)" />
              </div>
              <h2 style={{
                fontSize: '24px',
                fontWeight: 800,
                color: 'var(--text)',
                fontFamily: 'Space Grotesk, sans-serif',
                marginBlockStart: 0,
                marginBlockEnd: '8px',
                letterSpacing: '-0.02em',
              }}>
                آماده معامله!
              </h2>
              <p style={{ fontSize: '14px', color: 'var(--dim)', marginBlockStart: 0, marginBlockEnd: 0 }}>
                پیش از فعال‌سازی ربات معاملاتی، تنظیمات خود را مرور کنید.
              </p>
            </div>

            {/* Summary card */}
            <div style={{
              background: 'var(--bg2)',
              border: '1px solid var(--border)',
              borderRadius: '14px',
              padding: '20px 24px',
              marginBlockEnd: '20px',
            }}>
              {[
                { label: 'صرافی', value: exchange || 'متصل نشده' },
                { label: 'نوع معامله', value: marketType === 'spot' ? 'اسپات' : 'فیوچرز' },
                { label: 'سود هدف', value: `${targetProfit}%` },
                { label: 'معاملات در روز', value: `${tradesPerDay}×` },
                { label: 'سرمایه درگیر', value: `${capitalPct}%` },
              ].map(({ label, value }, i, arr) => (
                <div
                  key={label}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 0',
                    borderBlockEnd: i < arr.length - 1 ? '1px solid var(--border)' : 'none',
                  }}
                >
                  <span style={{ fontSize: '13px', color: 'var(--dim)' }}>{label}</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: 'var(--accent)', fontSize: '14px' }}>
                    {value}
                  </span>
                </div>
              ))}
            </div>

            <p style={{ fontSize: '12px', color: 'var(--faint)', textAlign: 'center', marginBlockStart: 0, marginBlockEnd: 0, lineHeight: 1.6 }}>
              با شروع، می‌پذیرید که معاملات خودکار ریسک دارد. عملکرد گذشته تضمینی برای نتایج آینده نیست.
            </p>
          </div>
        )}

        {/* ── Navigation buttons ── */}
        <div style={{
          display: 'flex',
          gap: '12px',
          marginBlockStart: '32px',
          alignItems: 'center',
        }}>
          {/* Back */}
          {step > 0 && (
            <button
              onClick={() => setStep((s) => s - 1)}
              disabled={loading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '13px 20px',
                border: '1px solid var(--border)',
                borderRadius: '10px',
                background: 'transparent',
                color: 'var(--dim)',
                fontSize: '14px',
                fontWeight: 500,
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: 'pointer',
                transition: 'all 0.2s',
                flexShrink: 0,
              }}
            >
              <ArrowLeft size={15} /> قبلی
            </button>
          )}

          {/* Skip (step 1 only) */}
          {step === 1 && (
            <button
              onClick={handleSkip}
              style={{
                padding: '13px 16px',
                border: 'none',
                background: 'transparent',
                color: 'var(--dim)',
                fontSize: '14px',
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              رد کردن
            </button>
          )}

          {/* Next / Launch */}
          <button
            onClick={handleNext}
            disabled={loading}
            style={{
              flex: 1,
              padding: '14px',
              border: 'none',
              borderRadius: '10px',
              background: 'var(--accent)',
              color: '#05121a',
              fontSize: '15px',
              fontWeight: 700,
              fontFamily: 'Space Grotesk, sans-serif',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.7 : 1,
              boxShadow: step === 3 ? '0 0 28px var(--accent)' : '0 0 16px rgba(0,229,255,0.3)',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
          >
            {loading ? 'لطفاً صبر کنید...' : step === 3 ? (
              <>شروع معاملات <Rocket size={16} /></>
            ) : step === 0 ? (
              <>شروع کنید <ArrowRight size={16} /></>
            ) : (
              <>بعدی <ArrowRight size={16} /></>
            )}
          </button>
        </div>
      </div>

      <style>{`
        input[type="range"] {
          -webkit-appearance: none;
          height: 4px;
          border-radius: 2px;
          background: var(--border);
        }
        input[type="range"]::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: var(--accent);
          cursor: pointer;
          box-shadow: 0 0 8px var(--accent);
        }
        input:focus {
          border-color: var(--accent) !important;
          box-shadow: 0 0 0 3px rgba(0,229,255,0.1) !important;
        }
      `}</style>
    </div>
  );
}
