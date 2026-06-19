import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Bot, BarChart3, DollarSign, Plus, Play, Pause, Eye, CheckCircle, X } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { useAuthStore } from '../stores/authStore';
import Layout from '../components/Layout';
import api from '../lib/api';

interface AdminStats {
  total_users: number;
  active_bots: number;
  total_trades: number;
  platform_pnl: number;
}

interface User {
  id: string;
  full_name: string;
  email: string;
  status: 'active' | 'paused' | 'inactive';
  exchanges_count: number;
  balance: number;
  pnl: number;
  bot_active: boolean;
}

export default function SuperAdmin() {
  const navigate = useNavigate();
  const { t } = useAppStore();
  const { isSuperAdmin } = useAuthStore();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [newUser, setNewUser] = useState({ full_name: '', email: '', password: '' });
  const [addLoading, setAddLoading] = useState(false);

  useEffect(() => {
    if (!isSuperAdmin) { navigate('/dashboard'); return; }
    fetchAll();
  }, [isSuperAdmin]);

  const fetchAll = async () => {
    try {
      setLoading(true);
      const [statsRes, usersRes] = await Promise.all([
        api.get('/admin/stats'),
        api.get('/admin/users'),
      ]);
      setStats(statsRes.data);
      setUsers(usersRes.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'بارگذاری با خطا مواجه شد');
    } finally {
      setLoading(false);
    }
  };

  const toggleBot = async (userId: string) => {
    try {
      await api.put(`/admin/users/${userId}/toggle-bot`);
      fetchAll();
    } catch {}
  };

  const addUser = async () => {
    try {
      setAddLoading(true);
      await api.post('/admin/users', newUser);
      setShowAddModal(false);
      setNewUser({ full_name: '', email: '', password: '' });
      fetchAll();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'افزودن کاربر با خطا مواجه شد');
    } finally {
      setAddLoading(false);
    }
  };

  const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  const fmtMoney = (n: number) => Math.round(n || 0).toLocaleString('en-US') + ' ت';

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 400 }}>
      <div style={{ width: 48, height: 48, border: '3px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
    </div>
  );

  if (error) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--red)' }}>{error}</div>
  );

  const statCards = [
    { label: 'کل کاربران', value: stats?.total_users ?? 0, icon: Users, color: 'var(--accent)' },
    { label: 'ربات‌های فعال', value: stats?.active_bots ?? 0, icon: Bot, color: 'var(--green)' },
    { label: 'کل معاملات', value: stats?.total_trades ?? 0, icon: BarChart3, color: 'var(--accent2)' },
    { label: 'سود/زیان پلتفرم', value: fmtMoney(stats?.platform_pnl ?? 0), icon: DollarSign, color: (stats?.platform_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' },
  ];

  return (
    <Layout title={t.navAdmin} subtitle="مدیریت کاربران پلتفرم و موتور یادگیری مشترک">
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        {statCards.map(card => (
          <div key={card.label} style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <div style={{ width: 40, height: 40, borderRadius: 12, background: `${card.color}20`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <card.icon size={20} style={{ color: card.color }} />
              </div>
              <span style={{ color: 'var(--faint)', fontSize: 13 }}>{card.label}</span>
            </div>
            <div style={{ fontFamily: 'JetBrains Mono', fontSize: 24, fontWeight: 700, color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* ML Model banner */}
      <div style={{ background: 'linear-gradient(135deg, rgba(75,224,255,0.08) 0%, rgba(255,92,200,0.08) 100%)', border: '1px solid var(--border)', borderRadius: 18, padding: '20px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--green)', boxShadow: '0 0 8px var(--green)' }} />
          <span style={{ fontFamily: 'Space Grotesk', fontWeight: 700, fontSize: 18, color: 'var(--text)' }}>مدل یادگیری مشترک</span>
          <span style={{ background: 'rgba(75,224,255,0.12)', border: '1px solid var(--accent)', borderRadius: 20, padding: '3px 12px', fontSize: 12, color: 'var(--accent)' }}>عملیاتی</span>
        </div>
        <div style={{ display: 'flex', gap: 32 }}>
          {[
            { label: 'در حال سرویس', value: `${stats?.total_users ?? 0} کاربر` },
            { label: 'درخواست در روز', value: '۱۲٬۸۴۷' },
            { label: 'آپ‌تایم', value: '۹۹٫۹٪' },
          ].map(item => (
            <div key={item.label} style={{ textAlign: 'center' }}>
              <div style={{ fontFamily: 'JetBrains Mono', fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>{item.value}</div>
              <div style={{ fontSize: 12, color: 'var(--faint)' }}>{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Users table */}
      <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 18, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h2 style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 700, margin: 0, color: 'var(--text)' }}>مدیریت کاربران</h2>
          <button onClick={() => setShowAddModal(true)} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--accent)', color: '#05121a', border: 'none', borderRadius: 12, padding: '10px 20px', fontWeight: 700, cursor: 'pointer' }}>
            <Plus size={16} /> افزودن کاربر
          </button>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['کاربر', 'صرافی‌ها', 'موجودی', 'وضعیت ربات', 'سود/زیان', 'عملیات'].map(col => (
                  <th key={col} style={{ textAlign: 'start', padding: '10px 12px', color: 'var(--faint)', fontSize: 12, fontWeight: 600, textTransform: 'uppercase', borderBottom: '1px solid var(--border)' }}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(user => (
                <tr key={user.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '14px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent), var(--accent2))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 13, color: '#05121a' }}>{getInitials(user.full_name)}</div>
                      <div>
                        <div style={{ color: 'var(--text)', fontWeight: 600 }}>{user.full_name}</div>
                        <div style={{ color: 'var(--dim)', fontSize: 12 }}>{user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '14px 12px' }}>
                    <span style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: '4px 10px', fontSize: 13, color: 'var(--dim)' }}>{user.exchanges_count}</span>
                  </td>
                  <td style={{ padding: '14px 12px', fontFamily: 'JetBrains Mono', color: 'var(--text)' }}>{fmtMoney(user.balance)}</td>
                  <td style={{ padding: '14px 12px' }}>
                    <span style={{ background: user.bot_active ? 'rgba(74,222,128,0.12)' : 'rgba(148,163,184,0.1)', border: `1px solid ${user.bot_active ? 'var(--green)' : 'var(--border)'}`, borderRadius: 20, padding: '4px 12px', fontSize: 12, color: user.bot_active ? 'var(--green)' : 'var(--dim)', fontWeight: 600 }}>
                      {user.bot_active ? 'فعال' : 'متوقف'}
                    </span>
                  </td>
                  <td style={{ padding: '14px 12px', fontFamily: 'JetBrains Mono', color: user.pnl >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 700 }}>{user.pnl >= 0 ? '+' : ''}{fmtMoney(user.pnl)}</td>
                  <td style={{ padding: '14px 12px' }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => toggleBot(user.id)} title={user.bot_active ? 'توقف ربات' : 'ادامه ربات'} style={{ background: user.bot_active ? 'rgba(251,191,36,0.12)' : 'rgba(74,222,128,0.12)', border: `1px solid ${user.bot_active ? 'var(--amber)' : 'var(--green)'}`, borderRadius: 8, width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: user.bot_active ? 'var(--amber)' : 'var(--green)' }}>
                        {user.bot_active ? <Pause size={15} /> : <Play size={15} />}
                      </button>
                      <button onClick={() => navigate(`/admin/users/${user.id}`)} title="مشاهده جزئیات" style={{ background: 'rgba(75,224,255,0.1)', border: '1px solid var(--accent)', borderRadius: 8, width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'var(--accent)' }}>
                        <Eye size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && (
            <div style={{ textAlign: 'center', padding: 48, color: 'var(--faint)' }}>کاربری یافت نشد</div>
          )}
        </div>
      </div>

      {/* Add User Modal */}
      {showAddModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 20, padding: 32, width: 420, position: 'relative' }}>
            <button onClick={() => setShowAddModal(false)} style={{ position: 'absolute', insetBlockStart: 16, insetInlineEnd: 16, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--dim)' }}><X size={20} /></button>
            <h3 style={{ fontFamily: 'Space Grotesk', margin: '0 0 24px', color: 'var(--text)' }}>افزودن کاربر جدید</h3>
            {([
              { field: 'full_name', label: 'نام کامل' },
              { field: 'email', label: 'ایمیل' },
              { field: 'password', label: 'رمز عبور' },
            ] as const).map(({ field, label }) => (
              <div key={field} style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', color: 'var(--faint)', fontSize: 12, marginBottom: 6 }}>{label}</label>
                <input type={field === 'password' ? 'password' : 'text'} value={newUser[field as keyof typeof newUser]} onChange={e => setNewUser(p => ({ ...p, [field]: e.target.value }))}
                  style={{ width: '100%', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', color: 'var(--text)', fontSize: 14, boxSizing: 'border-box', outline: 'none' }} />
              </div>
            ))}
            <button onClick={addUser} disabled={addLoading} style={{ width: '100%', background: 'var(--accent)', color: '#05121a', border: 'none', borderRadius: 12, padding: '12px 0', fontWeight: 700, fontSize: 15, cursor: 'pointer', marginTop: 8 }}>
              {addLoading ? 'در حال افزودن...' : 'افزودن کاربر'}
            </button>
          </div>
        </div>
      )}
    </div>
    </Layout>
  );
}
