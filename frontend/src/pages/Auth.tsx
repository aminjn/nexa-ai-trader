import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sun, Moon, Check, Shield, Zap, BarChart3, Eye, EyeOff, ChevronRight } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/api';
import Logo from '../components/Logo';
import { useIsMobile } from '../hooks/useIsMobile';

type Mode = 'login' | 'register';
type Tab = 'email' | 'mobile';

export default function Auth() {
  const navigate = useNavigate();
  const { lang, theme, t, dir, toggleTheme } = useAppStore();
  const { login } = useAuthStore();
  const isMobile = useIsMobile();

  const [mode, setMode] = useState<Mode>('login');
  const [tab, setTab] = useState<Tab>('email');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState<string[]>(['', '', '', '']);
  const [otpSent, setOtpSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPass, setShowPass] = useState(false);

  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) return;
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    if (value && index < 3) {
      otpRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  const handleSendOtp = async () => {
    setLoading(true);
    setError('');
    try {
      await api.post('/auth/send-otp', { phone });
      setOtpSent(true);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'ارسال کد با خطا مواجه شد');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      let data: any;
      if (mode === 'login') {
        if (tab === 'email') {
          const res = await api.post('/auth/login/email', { email, password });
          data = res.data;
        } else {
          const res = await api.post('/auth/verify-otp', { phone, code: otp.join('') });
          data = res.data;
        }
        login(data.access_token, data.user_id, data.is_superadmin, data.full_name);
        navigate('/dashboard');
      } else {
        const payload: any = { full_name: fullName };
        if (tab === 'email') {
          payload.email = email;
          payload.password = password;
        } else {
          payload.phone = phone;
          payload.code = otp.join('');
        }
        const res = await api.post('/auth/register', payload);
        data = res.data;
        login(data.access_token, data.user_id, data.is_superadmin, data.full_name);
        navigate('/onboarding');
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'احراز هویت ناموفق بود');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '12px 16px',
    background: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '10px',
    color: 'var(--text)',
    fontSize: '14px',
    fontFamily: 'Space Grotesk, sans-serif',
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

  const features = [
    { icon: <BarChart3 size={14} />, text: 'تحلیل بازار با هوش مصنوعی' },
    { icon: <Zap size={14} />, text: 'مدیریت خودکار سبد دارایی' },
    { icon: <Shield size={14} />, text: 'ارزیابی ریسک به‌صورت لحظه‌ای' },
  ];

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        direction: dir,
        fontFamily: 'Space Grotesk, sans-serif',
      }}
    >
      {/* ── Left Column (در موبایل مخفی) ── */}
      {!isMobile && (
      <div
        style={{
          width: '55%',
          background: 'var(--bg2)',
          display: 'flex',
          flexDirection: 'column',
          padding: '48px',
          position: 'relative',
          overflow: 'hidden',
          borderInlineEnd: '1px solid var(--border)',
        }}
      >
        {/* Decorative glow blobs */}
        <div style={{
          position: 'absolute',
          insetBlockStart: '-80px',
          insetInlineStart: '-80px',
          width: '320px',
          height: '320px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0,229,255,0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute',
          insetBlockEnd: '-60px',
          insetInlineEnd: '-60px',
          width: '260px',
          height: '260px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,0,200,0.07) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBlockEnd: '40px' }}>
          <Logo size={36} />
          <span style={{
            fontSize: '20px',
            fontWeight: 700,
            color: 'var(--text)',
            letterSpacing: '-0.02em',
            fontFamily: 'Space Grotesk, sans-serif',
          }}>
            NEXA AI Trader
          </span>
        </div>

        {/* Status pill */}
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          background: 'rgba(0,255,120,0.08)',
          border: '1px solid rgba(0,255,120,0.25)',
          borderRadius: '20px',
          padding: '6px 14px',
          marginBlockEnd: '40px',
          width: 'fit-content',
        }}>
          <span style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: '#00ff78',
            display: 'inline-block',
            boxShadow: '0 0 8px #00ff78',
            animation: 'statusPulse 2s infinite',
          }} />
          <span style={{ fontSize: '13px', color: '#00ff78', fontWeight: 500, fontFamily: 'JetBrains Mono, monospace' }}>
            سیستم فعال · مدل آماده
          </span>
        </div>

        {/* Hero title */}
        <h1 style={{
          fontSize: 'clamp(32px, 3.5vw, 44px)',
          fontWeight: 800,
          color: 'var(--text)',
          lineHeight: 1.15,
          marginBlockEnd: '16px',
          marginBlockStart: 0,
          letterSpacing: '-0.03em',
          fontFamily: 'Space Grotesk, sans-serif',
        }}>
          معاملات ارز دیجیتال
          <br />
          <span style={{
            background: 'linear-gradient(90deg, var(--accent), #ff00c8)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
          }}>
            با هوش مصنوعی
          </span>
        </h1>

        <p style={{
          fontSize: '16px',
          color: 'var(--dim)',
          lineHeight: 1.7,
          marginBlockEnd: '40px',
          marginBlockStart: 0,
          maxWidth: '420px',
        }}>
          مدل یادگیری ماشین آموزش‌دیده با ۵ سال داده بازار برای شناسایی بهترین فرصت‌های معاملاتی.
        </p>

        {/* Feature bullets */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBlockEnd: 'auto' }}>
          {features.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '8px',
                background: 'rgba(0,229,255,0.12)',
                border: '1px solid rgba(0,229,255,0.25)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent)',
                flexShrink: 0,
              }}>
                <Check size={14} />
              </div>
              <span style={{ fontSize: '15px', color: 'var(--text)' }}>{f.text}</span>
            </div>
          ))}
        </div>

        {/* Disclaimer */}
        <p style={{
          marginBlockStart: '48px',
          marginBlockEnd: 0,
          fontSize: '11px',
          color: 'var(--faint)',
          lineHeight: 1.6,
          maxWidth: '400px',
          fontFamily: 'JetBrains Mono, monospace',
        }}>
          * سود تضمین‌شده نیست. معامله ریسک دارد. عملکرد گذشته تضمینی برای نتایج آینده نیست؛ تنها مبلغی را وارد کنید که توان از دست دادن آن را دارید.
        </p>
      </div>
      )}

      {/* ── Right Column ── */}
      <div style={{
        width: isMobile ? '100%' : '45%',
        background: 'var(--bg)',
        display: 'flex',
        flexDirection: 'column',
        padding: isMobile ? '24px 18px' : '48px',
        position: 'relative',
      }}>
        {/* Top-right toggles */}
        <div style={{
          position: 'absolute',
          insetBlockStart: '24px',
          insetInlineEnd: '24px',
          display: 'flex',
          gap: '8px',
        }}>
          <button
            onClick={toggleTheme}
            title="تغییر تم"
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: 'var(--panel)',
              border: '1px solid var(--border)',
              color: 'var(--dim)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s',
            }}
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>

        {/* Vertically centered form area */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          maxWidth: '360px',
          marginInline: 'auto',
          width: '100%',
        }}>
          <h2 style={{
            fontSize: '26px',
            fontWeight: 700,
            color: 'var(--text)',
            marginBlockEnd: '24px',
            marginBlockStart: 0,
            letterSpacing: '-0.02em',
            fontFamily: 'Space Grotesk, sans-serif',
          }}>
            {mode === 'login' ? 'خوش آمدید' : 'ساخت حساب'}
          </h2>

          {/* Login / Register tab toggle */}
          <div style={{
            display: 'flex',
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: '10px',
            padding: '4px',
            marginBlockEnd: '20px',
          }}>
            {(['login', 'register'] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); }}
                style={{
                  flex: 1,
                  padding: '8px',
                  borderRadius: '7px',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500,
                  fontFamily: 'Space Grotesk, sans-serif',
                  background: mode === m ? 'var(--accent)' : 'transparent',
                  color: mode === m ? '#05121a' : 'var(--dim)',
                  transition: 'all 0.2s',
                }}
              >
                {m === 'login' ? 'ورود' : 'ثبت‌نام'}
              </button>
            ))}
          </div>

          {/* Email / Mobile sub-tabs */}
          <div style={{
            display: 'flex',
            gap: '4px',
            marginBlockEnd: '24px',
            borderBlockEnd: '1px solid var(--border)',
          }}>
            {(['email', 'mobile'] as Tab[]).map((tb) => (
              <button
                key={tb}
                onClick={() => {
                  setTab(tb);
                  setError('');
                  setOtpSent(false);
                  setOtp(['', '', '', '']);
                }}
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  borderBlockEnd: tab === tb ? '2px solid var(--accent)' : '2px solid transparent',
                  background: 'transparent',
                  color: tab === tb ? 'var(--accent)' : 'var(--dim)',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500,
                  fontFamily: 'Space Grotesk, sans-serif',
                  transition: 'all 0.2s',
                  marginBlockEnd: '-1px',
                }}
              >
                {tb === 'email' ? 'ایمیل' : 'موبایل'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Full name — register only */}
            {mode === 'register' && (
              <div>
                <label style={labelStyle}>نام کامل</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="نام و نام خانوادگی"
                  required
                  style={inputStyle}
                />
              </div>
            )}

            {tab === 'email' ? (
              <>
                <div>
                  <label style={labelStyle}>ایمیل</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="ایمیل خود را وارد کنید"
                    required
                    style={inputStyle}
                    dir="ltr"
                  />
                </div>

                <div>
                  <label style={labelStyle}>رمز عبور</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={showPass ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                      style={{ ...inputStyle, paddingInlineEnd: '44px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPass(!showPass)}
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
                      {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div>
                  <label style={labelStyle}>شماره موبایل</label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input
                      type="tel"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="۰۹۱۲ ۰۰۰ ۰۰۰۰"
                      required
                      style={{ ...inputStyle, flex: 1 }}
                    />
                    {!otpSent && (
                      <button
                        type="button"
                        onClick={handleSendOtp}
                        disabled={loading || !phone}
                        style={{
                          padding: '12px 16px',
                          background: 'var(--accent)',
                          border: 'none',
                          borderRadius: '10px',
                          color: '#05121a',
                          fontSize: '13px',
                          fontWeight: 600,
                          fontFamily: 'Space Grotesk, sans-serif',
                          cursor: loading || !phone ? 'not-allowed' : 'pointer',
                          opacity: loading || !phone ? 0.6 : 1,
                          whiteSpace: 'nowrap',
                          transition: 'all 0.2s',
                          flexShrink: 0,
                        }}
                      >
                        ارسال کد
                      </button>
                    )}
                  </div>
                </div>

                {otpSent && (
                  <div>
                    <label style={labelStyle}>کد تأیید را وارد کنید</label>
                    <div style={{ display: 'flex', gap: '10px', direction: 'ltr' }}>
                      {otp.map((digit, i) => (
                        <input
                          key={i}
                          ref={(el) => { otpRefs.current[i] = el; }}
                          type="text"
                          inputMode="numeric"
                          maxLength={1}
                          value={digit}
                          onChange={(e) => handleOtpChange(i, e.target.value.replace(/\D/g, ''))}
                          onKeyDown={(e) => handleOtpKeyDown(i, e)}
                          style={{
                            width: '56px',
                            height: '56px',
                            textAlign: 'center',
                            fontSize: '22px',
                            fontFamily: 'JetBrains Mono, monospace',
                            fontWeight: 700,
                            background: 'var(--bg2)',
                            border: digit ? '1px solid var(--accent)' : '1px solid var(--border)',
                            borderRadius: '10px',
                            color: 'var(--text)',
                            outline: 'none',
                            caretColor: 'var(--accent)',
                            transition: 'border-color 0.2s',
                          }}
                        />
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={handleSendOtp}
                      style={{
                        marginBlockStart: '8px',
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--accent)',
                        cursor: 'pointer',
                        fontSize: '13px',
                        fontFamily: 'Space Grotesk, sans-serif',
                        padding: 0,
                      }}
                    >
                      ارسال مجدد کد
                    </button>
                  </div>
                )}
              </>
            )}

            {/* Error banner */}
            {error && (
              <div style={{
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

            {/* Submit button */}
            <button
              type="submit"
              disabled={loading || (tab === 'mobile' && !otpSent)}
              style={{
                width: '100%',
                padding: '14px',
                background: 'var(--accent)',
                border: 'none',
                borderRadius: '10px',
                color: '#05121a',
                fontSize: '15px',
                fontWeight: 700,
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading || (tab === 'mobile' && !otpSent) ? 0.6 : 1,
                boxShadow: '0 0 24px var(--accent)',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                marginBlockStart: '4px',
              }}
            >
              {loading
                ? 'لطفاً صبر کنید...'
                : mode === 'login'
                  ? 'ورود'
                  : 'ساخت حساب'}
              {!loading && <ChevronRight size={16} />}
            </button>
          </form>

          {/* Switch mode */}
          <p style={{
            marginBlockStart: '20px',
            marginBlockEnd: 0,
            textAlign: 'center',
            fontSize: '14px',
            color: 'var(--dim)',
          }}>
            {mode === 'login' ? 'حساب ندارید؟ ' : 'حساب دارید؟ '}
            <button
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--accent)',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: 600,
                fontFamily: 'Space Grotesk, sans-serif',
                padding: 0,
              }}
            >
              {mode === 'login' ? 'ثبت‌نام' : 'ورود'}
            </button>
          </p>
        </div>
      </div>

      <style>{`
        @keyframes statusPulse {
          0%, 100% { opacity: 1; box-shadow: 0 0 8px #00ff78; }
          50% { opacity: 0.6; box-shadow: 0 0 18px #00ff78; }
        }
        input:focus {
          border-color: var(--accent) !important;
          box-shadow: 0 0 0 3px rgba(0,229,255,0.1) !important;
        }
      `}</style>
    </div>
  );
}
