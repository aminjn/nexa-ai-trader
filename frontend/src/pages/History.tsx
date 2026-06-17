import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
import api from '../lib/api'

interface Trade { id:number; pair:string; side:string; entry:number; exit:number; amount:number; pnl:number; exchange:string; trade_type:string; opened_at:string; closed_at:string }
interface HistoryRes { total:number; page:number; pages:number; trades:Trade[] }

export default function History() {
  const { t } = useAppStore()
  const [filter, setFilter] = useState<'all'|'profit'|'loss'>('all')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<HistoryRes|null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.get('/history/', { params: { page, profit_only: filter==='profit', loss_only: filter==='loss' } })
      .then(r => setData(r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [filter, page])

  const pnlColor = (v: number) => v >= 0 ? 'var(--green)' : 'var(--red)'
  const sideColor = (s: string) => ['buy','long'].includes(s) ? 'var(--accent)' : 'var(--accent2)'
  const sideLabel = (s: string) => ({ buy:t.buy, sell:t.sell, long:t.long, short:t.short }[s] || s.toUpperCase())
  const formatDate = (d: string) => d ? new Date(d).toLocaleDateString('fa-IR') + ' ' + new Date(d).toLocaleTimeString('fa-IR', { hour:'2-digit', minute:'2-digit' }) : '-'

  const filterBtn = (f: 'all'|'profit'|'loss', label: string) => (
    <span onClick={() => { setFilter(f); setPage(1) }} style={{ padding:'9px 18px', borderRadius:10, background:filter===f?'var(--accent)':'var(--bg3)', color:filter===f?'#05121a':'var(--dim)', fontSize:13, fontWeight:filter===f?600:400, cursor:'pointer', transition:'.2s' }}>{label}</span>
  )

  const exportCSV = () => {
    if (!data?.trades?.length) return
    const rows = [['pair','side','entry','exit','amount','pnl','date']]
    data.trades.forEach(tr => rows.push([tr.pair, tr.side, String(tr.entry), String(tr.exit||''), String(tr.amount), String(tr.pnl||''), tr.opened_at]))
    const csv = rows.map(r => r.join(',')).join('\n')
    const a = document.createElement('a'); a.href = `data:text/csv,${encodeURIComponent(csv)}`; a.download = 'trades.csv'; a.click()
  }

  return (
    <Layout title={t.navHistory} subtitle="تاریخچه کامل معاملات">
      <div className="fade-in" style={{ display:'flex', flexDirection:'column', gap:18 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
          <div style={{ display:'flex', gap:8 }}>
            {filterBtn('all', t.allTrades)}
            {filterBtn('profit', t.profitOnly)}
            {filterBtn('loss', t.lossOnly)}
          </div>
          <button onClick={exportCSV} style={{ padding:'9px 18px', border:'1px solid var(--border2)', borderRadius:10, background:'transparent', color:'var(--text)', fontSize:13, cursor:'pointer' }}>{t.export}</button>
        </div>

        <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:'8px 0', overflow:'hidden' }}>
          <div style={{ display:'grid', gridTemplateColumns:'1.4fr 1fr .8fr 1fr 1fr 1fr .9fr', gap:8, padding:'14px 24px', fontSize:12, color:'var(--faint)', borderBottom:'1px solid var(--border)' }}>
            <span>{t.pair}</span><span>{t.dateTime}</span><span>{t.side}</span><span>{t.entry}</span><span>{t.exit}</span><span>{t.amount}</span><span style={{ textAlign:'end' }}>{t.pnl}</span>
          </div>
          {loading ? (
            <div style={{ textAlign:'center', padding:40, color:'var(--faint)' }}>در حال بارگذاری...</div>
          ) : !data?.trades?.length ? (
            <div style={{ textAlign:'center', padding:40, color:'var(--faint)' }}>هیچ معامله‌ای یافت نشد</div>
          ) : data.trades.map(tr => (
            <div key={tr.id} style={{ display:'grid', gridTemplateColumns:'1.4fr 1fr .8fr 1fr 1fr 1fr .9fr', gap:8, padding:'14px 24px', fontSize:13, fontFamily:"'JetBrains Mono'", alignItems:'center', borderBottom:'1px solid var(--border)' }}>
              <span style={{ fontWeight:600, fontFamily:'Vazirmatn,sans-serif' }}>{tr.pair}</span>
              <span style={{ color:'var(--dim)' }}>{formatDate(tr.opened_at)}</span>
              <span style={{ color:sideColor(tr.side), fontWeight:600 }}>{sideLabel(tr.side)}</span>
              <span style={{ color:'var(--dim)' }}>{tr.entry?.toFixed(2)}</span>
              <span style={{ color:'var(--dim)' }}>{tr.exit?.toFixed(2)||'-'}</span>
              <span style={{ color:'var(--dim)' }}>{tr.amount?.toFixed(6)}</span>
              <span style={{ textAlign:'end', fontWeight:700, color:pnlColor(tr.pnl||0) }}>{(tr.pnl||0) >= 0 ? '+' : ''}{(tr.pnl||0).toFixed(4)}</span>
            </div>
          ))}
        </div>

        {data && data.pages > 1 && (
          <div style={{ display:'flex', justifyContent:'center', gap:8 }}>
            {Array.from({ length: data.pages }, (_, i) => (
              <button key={i} onClick={() => setPage(i+1)} style={{ width:36, height:36, border:`1px solid ${page===i+1?'var(--accent)':'var(--border)'}`, borderRadius:8, background:page===i+1?'var(--accent)':'transparent', color:page===i+1?'#05121a':'var(--dim)', cursor:'pointer', fontFamily:"'JetBrains Mono'" }}>{i+1}</button>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
