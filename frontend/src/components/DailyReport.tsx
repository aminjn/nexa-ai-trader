import { useState, useEffect, useCallback } from 'react'
import api from '../lib/api'
import { CalendarRange } from 'lucide-react'

interface DayRow { date: string; pnl: number; trades: number; wins: number; losses: number }
const fmt = (n: number) => Math.round(n || 0).toLocaleString('en-US')
const card: React.CSSProperties = { background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 18, padding: 20 }
const inputStyle: React.CSSProperties = { background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '8px 12px', color: 'var(--text)', fontSize: 13, outline: 'none', fontFamily: 'inherit' }

/** گزارش سود/زیان دقیق روزانه (به وقت تهران). userId برای سوپر ادمین جهت گزارش یک کاربر خاص. */
export default function DailyReport({ userId }: { userId?: number }) {
  const [rows, setRows] = useState<DayRow[]>([])
  const [total, setTotal] = useState(0)
  const [days, setDays] = useState(30)
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (start && end) { params.start = start; params.end = end } else { params.days = days }
      if (userId) params.user_id = userId
      const r = await api.get('/dashboard/daily-pnl', { params })
      setRows(r.data.days || []); setTotal(r.data.total_pnl || 0)
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [days, start, end, userId])

  useEffect(() => { load() }, [load])

  return (
    <div style={card}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 15 }}>
          <CalendarRange size={18} style={{ color: 'var(--accent)' }} /> گزارش سود/زیان روزانه
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {[7, 30, 90].map(d => (
            <button key={d} onClick={() => { setStart(''); setEnd(''); setDays(d) }}
              style={{ ...inputStyle, cursor: 'pointer', borderColor: (!start && days === d) ? 'var(--accent)' : 'var(--border)', color: (!start && days === d) ? 'var(--accent)' : 'var(--text)' }}>
              {d} روز
            </button>
          ))}
          <span style={{ fontSize: 12, color: 'var(--dim)' }}>یا بازه:</span>
          <input type="date" value={start} onChange={e => setStart(e.target.value)} style={inputStyle} />
          <span style={{ color: 'var(--dim)' }}>تا</span>
          <input type="date" value={end} onChange={e => setEnd(e.target.value)} style={inputStyle} />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 16, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ background: 'var(--bg2)', borderRadius: 12, padding: '12px 18px' }}>
          <div style={{ fontSize: 12, color: 'var(--dim)' }}>سود/زیان کل بازه</div>
          <div style={{ fontSize: 22, fontWeight: 800, fontFamily: 'JetBrains Mono', color: total >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {total >= 0 ? '+' : ''}{fmt(total)} ت
          </div>
        </div>
      </div>

      <div style={{ overflowX: 'auto', maxHeight: 340, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead><tr style={{ color: 'var(--dim)', textAlign: 'right', position: 'sticky', top: 0, background: 'var(--card-bg)' }}>
            {['تاریخ', 'سود/زیان', 'معاملات', 'برد', 'باخت'].map(c => <th key={c} style={{ padding: '8px 10px', fontWeight: 600 }}>{c}</th>)}
          </tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.date} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '9px 10px', fontFamily: 'JetBrains Mono' }}>{new Date(r.date).toLocaleDateString('fa-IR')}</td>
                <td style={{ padding: '9px 10px', fontFamily: 'JetBrains Mono', fontWeight: 700, color: r.pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                  {r.pnl >= 0 ? '+' : ''}{fmt(r.pnl)} ت
                </td>
                <td style={{ padding: '9px 10px' }}>{r.trades}</td>
                <td style={{ padding: '9px 10px', color: 'var(--green)' }}>{r.wins}</td>
                <td style={{ padding: '9px 10px', color: 'var(--red)' }}>{r.losses}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--faint)' }}>
                {loading ? 'در حال بارگذاری…' : 'در این بازه معاملهٔ بسته‌شده‌ای نیست.'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
