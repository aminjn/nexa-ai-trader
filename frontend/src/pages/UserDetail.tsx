import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Pause, Play, Key } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useAppStore } from '../stores/appStore';
import Layout from '../components/Layout';
import api from '../lib/api';

interface UserData {
  id: string;
  full_name: string;
  email: string;
  status: 'active' | 'paused' | 'inactive';
  balance: number;
  today_pnl: number;
  total_trades: number;
  win_rate: number;
  equity_curve: { date: string; value: number }[];
  exchanges: { name: string; api_key: string }[];
  recent_trades: { pair: string; side: string; pnl: number; created_at: string }[];
  created_at: string;
  bot_active: boolean;
}

export default function UserDetail() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { t } = useAppStore();
  const [user, setUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [toggling, setToggling] = useState(false);

  useEffect(() => { fetchUser(); }, [id]);

  const fetchUser = async () => {
    try {
      setLoading(true);
      const res = await api.get(`/admin/users/${id}`);
      setUser(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'بارگذاری کاربر با خطا مواجه شد');
    } finally {
      setLoading(false);
    }
  };

  const toggleBot = async () => {
    if (!user) return;
    try {
      setToggling(true);
      await api.put(`/admin/users/${id}/toggle-bot`);
      fetchUser();
    } catch {} finally { setToggling(false); }
  };

  const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  const maskKey = (key: string) => key.slice(0, 4) + '••••••••' + key.slice(-4);
  const fmtMoney = (n: number) => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2 });
  const fmtDate = (d: string) => new Date(d).toLocaleDateString();

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400 }}>
      <div style={{ width: 48, height: 48, border: '3px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
    </div>
  );

  if (error || !user) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--red)' }}>{error || 'کاربر یافت نشد'}</div>
  );

  const statusColor = { active: 'var(--green)', paused: 'var(--amber)', inactive: 'var(--dim)' }[user.status];
  const statusLabel = { active: 'فعال', paused: 'متوقف', inactive: 'غیرفعال' }[user.status];

  return (
    <Layout title={user.full_name} subtitle="جزئیات حساب کاربر و تاریخچه معاملات">
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <button onClick={() => navigate('/admin')} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, width: 40, height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--dim)' }}>
            <ArrowLeft size={18} />
          </button>
          <div style={{ width: 72, height: 72, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent), var(--accent2))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, fontWeight: 800, color: '#05121a' }}>
            {getInitials(user.full_name)}
          </div>
          <div>
            <h1 style={{ fontFamily: 'Space Grotesk', fontSize: 24, fontWeight: 800, margin: '0 0 6px', color: 'var(--text)' }}>{user.full_name}</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ background: `${statusColor}20`, border: `1px solid ${statusColor}`, borderRadius: 20, padding: '3px 12px', fontSize: 12, color: statusColor, fontWeight: 600 }}>{statusLabel}</span>
              <span style={{ color: 'var(--dim)', fontSize: 13 }}>{user.email}</span>
              <span style={{ color: 'var(--faint)', fontSize: 12 }}>عضویت از {fmtDate(user.created_at)}</span>
            </div>
          </div>
        </div>
        <button onClick={toggleBot} disabled={toggling} style={{ display: 'flex', alignItems: 'center', gap: 8, background: user.bot_active ? 'rgba(251,191,36,0.12)' : 'var(--accent)', border: user.bot_active ? '1px solid var(--amber)' : 'none', borderRadius: 12, padding: '12px 24px', fontWeight: 700, cursor: 'pointer', color: user.bot_active ? 'var(--amber)' : '#05121a' }}>
          {user.bot_active ? <><Pause size={16} /> توقف ربات</> : <><Play size={16} /> ادامه ربات</>}
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        {[
          { label: 'موجودی', value: fmtMoney(user.balance), color: 'var(--text)' },
          { label: 'سود/زیان امروز', value: (user.today_pnl >= 0 ? '+' : '') + fmtMoney(user.today_pnl), color: user.today_pnl >= 0 ? 'var(--green)' : 'var(--red)' },
          { label: 'کل معاملات', value: user.total_trades.toString(), color: 'var(--text)' },
          { label: 'نرخ موفقیت', value: user.win_rate.toFixed(1) + '%', color: 'var(--accent)' },
        ].map(stat => (
          <div key={stat.label} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }}>
            <div style={{ color: 'var(--faint)', fontSize: 12, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{stat.label}</div>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: 22, fontWeight: 700, color: stat.color }}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* Equity Curve */}
      <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }}>
        <h3 style={{ fontFamily: 'Space Grotesk', margin: '0 0 20px', color: 'var(--text)' }}>نمودار دارایی</h3>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={user.equity_curve} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="userEquityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" stroke="var(--faint)" tick={{ fontSize: 11 }} />
            <YAxis stroke="var(--faint)" tick={{ fontSize: 11, fontFamily: 'JetBrains Mono' }} tickFormatter={v => '$' + v.toLocaleString()} />
            <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text)' }} formatter={(v: number) => ['$' + v.toLocaleString(), 'دارایی']} />
            <Area type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2} fill="url(#userEquityGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* API Keys */}
      <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }}>
        <h3 style={{ fontFamily: 'Space Grotesk', margin: '0 0 16px', color: 'var(--text)' }}>صرافی‌های متصل</h3>
        {user.exchanges.length === 0 ? (
          <p style={{ color: 'var(--faint)' }}>هیچ صرافی متصل نیست</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {user.exchanges.map((ex, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', background: 'var(--bg2)', borderRadius: 12, border: '1px solid var(--border)' }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent), var(--accent2))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#05121a' }}>{ex.name.slice(0, 2).toUpperCase()}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ color: 'var(--text)', fontWeight: 600 }}>{ex.name}</div>
                  <div style={{ fontFamily: 'JetBrains Mono', fontSize: 12, color: 'var(--dim)', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Key size={11} /> {maskKey(ex.api_key || '0000000000000000')}
                  </div>
                </div>
                <span style={{ background: 'rgba(74,222,128,0.12)', border: '1px solid var(--green)', borderRadius: 20, padding: '3px 12px', fontSize: 11, color: 'var(--green)' }}>متصل</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Trades */}
      <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }}>
        <h3 style={{ fontFamily: 'Space Grotesk', margin: '0 0 16px', color: 'var(--text)' }}>معاملات اخیر</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['جفت‌ارز', 'جهت', 'سود/زیان', 'تاریخ'].map(col => (
                <th key={col} style={{ textAlign: 'start', padding: '8px 12px', color: 'var(--faint)', fontSize: 12, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {user.recent_trades.slice(0, 10).map((trade, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '12px', color: 'var(--accent)', fontWeight: 700 }}>{trade.pair}</td>
                <td style={{ padding: '12px' }}>
                  <span style={{ background: trade.side === 'BUY' ? 'rgba(75,224,255,0.12)' : 'rgba(255,92,200,0.12)', border: `1px solid ${trade.side === 'BUY' ? 'var(--accent)' : 'var(--accent2)'}`, borderRadius: 8, padding: '3px 10px', fontSize: 12, color: trade.side === 'BUY' ? 'var(--accent)' : 'var(--accent2)', fontWeight: 600 }}>{trade.side}</span>
                </td>
                <td style={{ padding: '12px', fontFamily: 'JetBrains Mono', color: trade.pnl >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>{trade.pnl >= 0 ? '+' : ''}{fmtMoney(trade.pnl)}</td>
                <td style={{ padding: '12px', color: 'var(--dim)', fontSize: 12 }}>{fmtDate(trade.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {user.recent_trades.length === 0 && <p style={{ color: 'var(--faint)', textAlign: 'center', padding: 24 }}>هنوز معامله‌ای نیست</p>}
      </div>
    </div>
    </Layout>
  );
}
