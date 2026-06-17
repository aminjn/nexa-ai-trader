import React, { useState, useEffect } from 'react';
import { UserCheck, Shield, TrendingDown, BarChart2, AlertTriangle, Save, Check } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { useAuthStore } from '../stores/authStore';
import Layout from '../components/Layout';
import api from '../lib/api';

interface Settings {
  max_profit: number;
  max_trades_per_day: number;
  max_leverage: number;
  platform_fee: number;
  auto_approve: boolean;
  require_kyc: boolean;
  allow_short: boolean;
  allow_futures: boolean;
  maintenance_mode: boolean;
}

const defaultSettings: Settings = {
  max_profit: 5, max_trades_per_day: 100, max_leverage: 10, platform_fee: 5,
  auto_approve: false, require_kyc: true, allow_short: true, allow_futures: true, maintenance_mode: false
};

export default function AdminSettings() {
  const { t } = useAppStore();
  const { isSuperAdmin } = useAuthStore();
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const res = await api.get('/admin/settings');
      setSettings(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'بارگذاری تنظیمات با خطا مواجه شد');
    } finally {
      setLoading(false);
    }
  };

  const save = async () => {
    try {
      setSaving(true);
      await api.put('/admin/settings', settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'ذخیره با خطا مواجه شد');
    } finally {
      setSaving(false);
    }
  };

  const setVal = <K extends keyof Settings>(key: K, val: Settings[K]) => setSettings(p => ({ ...p, [key]: val }));

  const sliders = [
    { key: 'max_profit' as const, label: 'حداکثر سود هر معامله', min: 1, max: 10, step: 0.5, suffix: '%' },
    { key: 'max_trades_per_day' as const, label: 'حداکثر معاملات روزانه', min: 10, max: 200, step: 5, suffix: '' },
    { key: 'max_leverage' as const, label: 'حداکثر اهرم', min: 1, max: 25, step: 1, suffix: 'x' },
    { key: 'platform_fee' as const, label: 'کارمزد پلتفرم', min: 0, max: 40, step: 1, suffix: '%' },
  ];

  const toggles = [
    { key: 'auto_approve' as const, label: 'تأیید خودکار کاربران', desc: 'تأیید خودکار ثبت‌نام کاربران جدید', icon: UserCheck },
    { key: 'require_kyc' as const, label: 'الزام احراز هویت', desc: 'الزام احراز هویت پیش از معامله', icon: Shield },
    { key: 'allow_short' as const, label: 'اجازه معاملات شورت', desc: 'فعال‌سازی معاملات شورت برای همه کاربران', icon: TrendingDown },
    { key: 'allow_futures' as const, label: 'اجازه معاملات فیوچرز', desc: 'فعال‌سازی قراردادهای فیوچرز برای همه کاربران', icon: BarChart2 },
    { key: 'maintenance_mode' as const, label: 'حالت تعمیرات', desc: 'توقف تمام فعالیت‌های معاملاتی در کل پلتفرم', icon: AlertTriangle, danger: true },
  ];

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400 }}>
      <div style={{ width: 48, height: 48, border: '3px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
    </div>
  );

  return (
    <Layout title={t.navSettings} subtitle="تنظیمات و محدودیت‌های کل پلتفرم">
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      {error && <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--red)', borderRadius: 12, padding: '12px 16px', color: 'var(--red)' }}>{error}</div>}
      {saved && (
        <div style={{ background: 'rgba(74,222,128,0.1)', border: '1px solid var(--green)', borderRadius: 12, padding: '12px 16px', color: 'var(--green)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Check size={16} /> تنظیمات با موفقیت ذخیره شد
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Left - Guardrails */}
        <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }}>
          <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 700, margin: '0 0 24px', color: 'var(--text)' }}>محدودیت‌های معاملاتی</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
            {sliders.map(s => (
              <div key={s.key}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                  <span style={{ color: 'var(--dim)', fontSize: 14 }}>{s.label}</span>
                  <span style={{ fontFamily: 'JetBrains Mono', color: 'var(--accent)', fontWeight: 700, fontSize: 15 }}>{settings[s.key]}{s.suffix}</span>
                </div>
                <input type="range" min={s.min} max={s.max} step={s.step} value={settings[s.key] as number}
                  onChange={e => setVal(s.key, parseFloat(e.target.value) as any)}
                  style={{ width: '100%', accentColor: 'var(--accent)', height: 6, borderRadius: 3, outline: 'none', cursor: 'pointer' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                  <span style={{ color: 'var(--faint)', fontSize: 11 }}>{s.min}{s.suffix}</span>
                  <span style={{ color: 'var(--faint)', fontSize: 11 }}>{s.max}{s.suffix}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right - Platform Controls */}
        <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }}>
          <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 700, margin: '0 0 24px', color: 'var(--text)' }}>کنترل‌های پلتفرم</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {toggles.map((tog, i) => {
              const Icon = tog.icon;
              const isOn = settings[tog.key] as boolean;
              return (
                <div key={tog.key} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 0', borderBottom: i < toggles.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  <div style={{ width: 38, height: 38, borderRadius: 10, background: tog.danger && isOn ? 'rgba(239,68,68,0.12)' : 'var(--bg2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Icon size={18} style={{ color: tog.danger && isOn ? 'var(--red)' : 'var(--dim)' }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ color: tog.danger && isOn ? 'var(--red)' : 'var(--text)', fontWeight: 600, fontSize: 14 }}>{tog.label}</div>
                    <div style={{ color: 'var(--faint)', fontSize: 12, marginTop: 2 }}>{tog.desc}</div>
                  </div>
                  <div onClick={() => setVal(tog.key, !isOn as any)} style={{ width: 48, height: 26, borderRadius: 13, background: isOn ? (tog.danger ? 'var(--red)' : 'var(--accent)') : 'var(--bg3)', position: 'relative', cursor: 'pointer', transition: 'background 0.3s', flexShrink: 0 }}>
                    <div style={{ position: 'absolute', top: 3, insetInlineStart: isOn ? 24 : 3, width: 20, height: 20, borderRadius: '50%', background: 'white', transition: 'inset-inline-start 0.3s', boxShadow: '0 1px 4px rgba(0,0,0,0.3)' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Save button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={save} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: 10, background: 'var(--accent)', color: '#05121a', border: 'none', borderRadius: 14, padding: '14px 32px', fontWeight: 800, fontSize: 15, cursor: 'pointer', fontFamily: 'Space Grotesk', boxShadow: '0 0 20px rgba(75,224,255,0.3)', opacity: saving ? 0.7 : 1 }}>
          <Save size={18} /> {saving ? 'در حال ذخیره...' : 'ذخیره تنظیمات'}
        </button>
      </div>
    </div>
    </Layout>
  );
}
