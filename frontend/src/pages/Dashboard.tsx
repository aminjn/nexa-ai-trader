import { useState, useEffect } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from 'recharts'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
import api from '../lib/api'
import { Sparkles, TrendingUp, Activity, RefreshCw } from 'lucide-react'
import toast from 'react-hot-toast'

interface Stats { total_equity:number; today_pnl:number; today_pnl_pct:number; total_trades_24h:number; win_rate:number }
interface Trade { id:number; pair:string; side:string; entry:number; exit:number; pnl:number; pnl_pct:number; status:string; opened_at:string; exchange:string }
interface EquityPoint { date:string; value:number }
interface ActivityEvent { time:string; message:string; level:string }
interface Signal { pair:string; signal:string; signal_fa:string; confidence:number }
interface Holding { currency:string; amount:number; value_toman:number; exchange:string }
interface Position { id:number; pair:string; amount:number; entry_price:number; current_price:number; target_sell_price:number; stop_price:number; pnl_pct:number; target_profit:number; stop_loss:number }

const StatCard = ({ label, value, sub, subColor }: { label:string; value:string; sub?:string; subColor?:string }) => (
  <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:'18px 20px' }}>
    <div style={{ fontSize:13, color:'var(--dim)', marginBottom:8 }}>{label}</div>
    <div style={{ fontFamily:"'JetBrains Mono'", fontSize:26, fontWeight:700 }}>{value}</div>
    {sub && <div style={{ fontSize:12, color:subColor||'var(--dim)', marginTop:6, fontFamily:"'JetBrains Mono'" }}>{sub}</div>}
  </div>
)

export default function Dashboard() {
  const { t } = useAppStore()
  const [stats, setStats] = useState<Stats|null>(null)
  const [equity, setEquity] = useState<EquityPoint[]>([])
  const [trades, setTrades] = useState<Trade[]>([])
  const [btcPrice, setBtcPrice] = useState(0)
  const [loading, setLoading] = useState(true)
  const [activity, setActivity] = useState<ActivityEvent[]>([])
  const [runningNow, setRunningNow] = useState(false)
  const [signals, setSignals] = useState<Signal[]>([])
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [positions, setPositions] = useState<Position[]>([])
  const [importing, setImporting] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const [s, eq, tr, btc, act, sig, hold, pos] = await Promise.all([
          api.get('/dashboard/stats'),
          api.get('/dashboard/equity-curve'),
          api.get('/dashboard/recent-trades'),
          api.get('/dashboard/btc-price'),
          api.get('/strategy/activity'),
          api.get('/dashboard/signals'),
          api.get('/dashboard/holdings'),
          api.get('/dashboard/positions'),
        ])
        setStats(s.data)
        setEquity(eq.data.data || [])
        setTrades(tr.data || [])
        setBtcPrice(btc.data.price || 0)
        setActivity(act.data.events || [])
        setSignals(sig.data.signals || [])
        setHoldings(hold.data.holdings || [])
        setPositions(pos.data.positions || [])
      } catch {} finally { setLoading(false) }
    }
    load()
    const iv = setInterval(load, 15000)
    return () => clearInterval(iv)
  }, [])

  const [testing, setTesting] = useState(false)

  const runNow = async () => {
    setRunningNow(true)
    try {
      const r = await api.post('/strategy/bot/run-now')
      toast.success(r.data.message || 'بررسی بازار انجام شد')
      const act = await api.get('/strategy/activity')
      setActivity(act.data.events || [])
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'خطا در بررسی بازار')
    } finally { setRunningNow(false) }
  }

  const testTrade = async () => {
    if (!window.confirm('⚠️ این یک سفارش خرید واقعی با پول واقعی است (حداقل مبلغ). ادامه می‌دهید؟')) return
    setTesting(true)
    try {
      const r = await api.post('/strategy/bot/test-trade', { pair: 'BTC/RLS' })
      if (r.data.ok) toast.success(r.data.message)
      else toast.error(r.data.message)
      const act = await api.get('/strategy/activity')
      setActivity(act.data.events || [])
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'خطا در تست معامله')
    } finally { setTesting(false) }
  }

  const importPositions = async () => {
    setImporting(true)
    try {
      const r = await api.post('/strategy/import-positions')
      toast.success(r.data.message || 'انجام شد')
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'خطا')
    } finally { setImporting(false) }
  }

  const fmtTime = (iso: string) => {
    try { return new Date(iso).toLocaleTimeString('fa-IR', { hour:'2-digit', minute:'2-digit', second:'2-digit' }) } catch { return '' }
  }

  const pnlColor = (v: number) => v >= 0 ? 'var(--green)' : 'var(--red)'
  const sideColor = (s: string) => ['buy','long'].includes(s) ? 'var(--accent)' : 'var(--accent2)'
  const sideLabel = (s: string) => ({ buy:t.buy, sell:t.sell, long:t.long, short:t.short }[s] || s.toUpperCase())

  const allocation = [
    { name:'BTC', pct:45, color:'var(--amber)' },
    { name:'ETH', pct:30, color:'var(--accent)' },
    { name:'SOL', pct:15, color:'var(--accent2)' },
    { name:'سایر', pct:10, color:'var(--green)' },
  ]

  return (
    <Layout title={t.navDashboard} subtitle={t.last90}>
      <div className="fade-in" style={{ display:'flex', flexDirection:'column', gap:22 }}>
        {/* Stats */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16 }}>
          <StatCard label={t.totalEquity} value={`$${stats?.total_equity?.toFixed(2)||'0.00'}`} sub={stats?.today_pnl_pct ? `${stats.today_pnl_pct>=0?'+':''}${stats.today_pnl_pct}%` : undefined} subColor={pnlColor(stats?.today_pnl_pct||0)} />
          <StatCard label={t.todayPnl} value={`$${stats?.today_pnl?.toFixed(4)||'0'}`} subColor={pnlColor(stats?.today_pnl||0)} />
          <StatCard label={t.winRate} value={`${stats?.win_rate||0}%`} sub="↑ نرخ موفقیت" subColor="var(--green)" />
          <StatCard label={t.trades24h} value={`${stats?.total_trades_24h||0}`} sub="معاملات" />
        </div>

        {/* فعالیت زنده ربات */}
        <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:22 }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:16 }}>
            <div style={{ display:'flex', alignItems:'center', gap:10 }}>
              <Activity size={18} style={{ color:'var(--accent)' }} />
              <span style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>فعالیت زنده ربات</span>
            </div>
            <div style={{ display:'flex', gap:10 }}>
              <button onClick={testTrade} disabled={testing} style={{ display:'flex', alignItems:'center', gap:7, padding:'9px 16px', border:'1px solid var(--amber)', borderRadius:11, background:'color-mix(in srgb,var(--amber) 12%,transparent)', color:'var(--amber)', fontWeight:700, fontFamily:'inherit', fontSize:13, cursor:testing?'not-allowed':'pointer', opacity:testing?0.7:1 }}>
                🧪 تست معامله واقعی
              </button>
              <button onClick={runNow} disabled={runningNow} style={{ display:'flex', alignItems:'center', gap:7, padding:'9px 18px', border:'none', borderRadius:11, background:'var(--accent)', color:'#05121a', fontWeight:700, fontFamily:'inherit', fontSize:13, cursor:runningNow?'not-allowed':'pointer', opacity:runningNow?0.7:1 }}>
                <RefreshCw size={14} style={{ animation: runningNow ? 'spin 1s linear infinite' : 'none' }} />
                بررسی فوری بازار
              </button>
            </div>
          </div>
          <div style={{ maxHeight:280, overflowY:'auto', display:'flex', flexDirection:'column', gap:8 }}>
            {activity.length === 0 ? (
              <div style={{ color:'var(--faint)', fontSize:13, textAlign:'center', padding:'24px 0' }}>
                هنوز فعالیتی ثبت نشده. ربات را روشن کن یا «بررسی فوری بازار» را بزن.
              </div>
            ) : activity.map((ev, i) => (
              <div key={i} style={{ display:'flex', alignItems:'center', gap:12, padding:'10px 14px', background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:10 }}>
                <span style={{ fontFamily:"'JetBrains Mono'", fontSize:11, color:'var(--faint)', flexShrink:0 }}>{fmtTime(ev.time)}</span>
                <span style={{ fontSize:13, color: ev.level==='error' ? 'var(--red)' : 'var(--text)' }}>{ev.message}</span>
              </div>
            ))}
          </div>
        </div>

        {/* معاملات باز — کی و چه قیمتی می‌فروشد */}
        <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:22 }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:16 }}>
            <span style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>معاملات باز (هدف فروش)</span>
            <button onClick={importPositions} disabled={importing} style={{ padding:'8px 16px', border:'1px solid var(--border2)', borderRadius:10, background:'transparent', color:'var(--text)', fontWeight:600, fontFamily:'inherit', fontSize:12, cursor:importing?'not-allowed':'pointer' }}>
              📥 وارد کردن معاملات از نوبیتکس
            </button>
          </div>
          {positions.length === 0 ? (
            <div style={{ textAlign:'center', color:'var(--faint)', padding:20, fontSize:13 }}>
              معامله بازی وجود ندارد. اگر در نوبیتکس خریدی داری، «وارد کردن معاملات» را بزن.
            </div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr 1fr', gap:8, padding:'0 12px 8px', fontSize:11, color:'var(--faint)' }}>
                <span>جفت‌ارز</span><span>قیمت خرید</span><span>قیمت فعلی</span><span>🎯 فروش در</span><span style={{textAlign:'end'}}>سود/زیان</span>
              </div>
              {positions.map(p => (
                <div key={p.id} style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr 1fr', gap:8, padding:12, borderRadius:11, alignItems:'center', fontSize:13, fontFamily:"'JetBrains Mono'", background:'var(--bg3)' }}>
                  <span style={{ fontWeight:700 }}>{p.pair}</span>
                  <span style={{ color:'var(--dim)' }}>{p.entry_price.toLocaleString()}</span>
                  <span style={{ color:'var(--dim)' }}>{p.current_price.toLocaleString()}</span>
                  <span style={{ color:'var(--green)', fontWeight:700 }}>{p.target_sell_price.toLocaleString()}</span>
                  <span style={{ textAlign:'end', fontWeight:700, color:pnlColor(p.pnl_pct) }}>{p.pnl_pct>=0?'+':''}{p.pnl_pct}%</span>
                </div>
              ))}
              <p style={{ fontSize:11, color:'var(--faint)', margin:'6px 0 0' }}>
                ربات وقتی قیمت به «هدف فروش» (سود {positions[0]?.target_profit}٪) یا حد ضرر ({positions[0]?.stop_loss}٪-) برسد، خودکار می‌فروشد.
              </p>
            </div>
          )}
        </div>

        {/* Charts */}
        <div style={{ display:'grid', gridTemplateColumns:'1.6fr 1fr', gap:16 }}>
          <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:22 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
              <div>
                <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>{t.equityCurve}</div>
                <div style={{ fontSize:12, color:'var(--dim)' }}>{t.last90}</div>
              </div>
              <div style={{ display:'flex', gap:6 }}>
                <span style={{ padding:'6px 12px', borderRadius:8, background:'var(--accent)', color:'#05121a', fontSize:12, fontWeight:600, fontFamily:"'JetBrains Mono'" }}>۹۰ روز</span>
              </div>
            </div>
            <div style={{ height:280 }}>
              {equity.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={equity}>
                    <defs>
                      <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                    <XAxis dataKey="date" tick={{ fontSize:11, fill:'var(--faint)' }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fontSize:11, fill:'var(--faint)' }} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ background:'var(--bg2)', border:'1px solid var(--border)', borderRadius:10, color:'var(--text)', fontFamily:"'JetBrains Mono'" }} />
                    <Area type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2} fill="url(#eqGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', color:'var(--faint)', fontSize:14 }}>
                  {loading ? 'در حال بارگذاری...' : 'هنوز معامله‌ای ثبت نشده'}
                </div>
              )}
            </div>
          </div>
          <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:22, display:'flex', flexDirection:'column' }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'start', marginBottom:14 }}>
              <div>
                <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>BTC/USDT</div>
                <div style={{ fontFamily:"'JetBrains Mono'", fontSize:22, fontWeight:700, marginTop:4 }}>${btcPrice.toLocaleString()}</div>
              </div>
              <span style={{ padding:'5px 10px', borderRadius:8, background:'color-mix(in srgb,var(--green) 16%,transparent)', color:'var(--green)', fontSize:12, fontWeight:600, fontFamily:"'JetBrains Mono'" }}>زنده</span>
            </div>
            <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--faint)', fontSize:13 }}>
              {btcPrice > 0 ? `$${btcPrice.toLocaleString()}` : 'در حال دریافت...'}
            </div>
          </div>
        </div>

        {/* Trades + AI */}
        <div style={{ display:'grid', gridTemplateColumns:'1.6fr 1fr', gap:16 }}>
          <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:22 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
              <div style={{ fontFamily:"'Space Grotesk'", fontSize:17, fontWeight:600 }}>{t.recentTrades}</div>
              <span style={{ fontSize:13, color:'var(--accent)', cursor:'pointer' }}>{t.viewAll}</span>
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1.4fr .8fr 1fr 1fr .8fr', gap:8, padding:'0 12px 10px', fontSize:12, color:'var(--faint)' }}>
              <span>{t.pair}</span><span>{t.side}</span><span>{t.entry}</span><span>{t.exit}</span><span style={{ textAlign:'end' }}>{t.pnl}</span>
            </div>
            {trades.length === 0 ? (
              <div style={{ textAlign:'center', color:'var(--faint)', padding:24, fontSize:14 }}>هنوز معامله‌ای ثبت نشده</div>
            ) : trades.map(tr => (
              <div key={tr.id} style={{ display:'grid', gridTemplateColumns:'1.4fr .8fr 1fr 1fr .8fr', gap:8, padding:12, borderRadius:11, alignItems:'center', fontSize:13, fontFamily:"'JetBrains Mono'", background:'var(--bg3)', marginBottom:2 }}>
                <span style={{ fontWeight:600, fontFamily:'Vazirmatn,sans-serif' }}>{tr.pair}</span>
                <span style={{ color:sideColor(tr.side), fontWeight:600 }}>{sideLabel(tr.side)}</span>
                <span style={{ color:'var(--dim)' }}>{tr.entry?.toFixed(2)}</span>
                <span style={{ color:'var(--dim)' }}>{tr.exit?.toFixed(2)||'-'}</span>
                <span style={{ textAlign:'end', fontWeight:700, color:pnlColor(tr.pnl||0) }}>{tr.pnl >= 0 ? '+' : ''}{tr.pnl?.toFixed(4)||'0'}</span>
              </div>
            ))}
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            <div style={{ background:'linear-gradient(150deg,color-mix(in srgb,var(--accent2) 18%,var(--card-bg)),var(--card-bg))', border:'1px solid var(--border2)', borderRadius:18, padding:20 }}>
              <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:14 }}>
                <Sparkles size={22} color="var(--accent2)" />
                <span style={{ fontFamily:"'Space Grotesk'", fontWeight:600, fontSize:15 }}>سیگنال‌های فعلی مدل</span>
              </div>
              {signals.length === 0 ? (
                <p style={{ fontSize:13, color:'var(--faint)', margin:0 }}>مدل آموزش ندیده یا داده‌ای موجود نیست.</p>
              ) : signals.map(s => {
                const c = s.signal === 'BUY' ? 'var(--green)' : s.signal === 'SELL' ? 'var(--red)' : 'var(--amber)'
                return (
                  <div key={s.pair} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'10px 0', borderBottom:'1px solid var(--border)' }}>
                    <span style={{ fontWeight:600, fontFamily:"'JetBrains Mono'" }}>{s.pair}</span>
                    <span style={{ display:'flex', alignItems:'center', gap:8 }}>
                      <span style={{ padding:'3px 12px', borderRadius:999, background:`color-mix(in srgb,${c} 16%,transparent)`, color:c, fontSize:13, fontWeight:700 }}>{s.signal_fa}</span>
                      <span style={{ fontSize:12, color:'var(--dim)', fontFamily:"'JetBrains Mono'" }}>{s.confidence}٪</span>
                    </span>
                  </div>
                )
              })}
              <p style={{ fontSize:11, color:'var(--faint)', margin:'12px 0 0', lineHeight:1.7 }}>
                ربات فقط روی سیگنال «خرید» با اطمینان کافی معامله می‌کند.
              </p>
            </div>
            <div style={{ background:'var(--card-bg)', border:'1px solid var(--border)', borderRadius:18, padding:20 }}>
              <div style={{ fontFamily:"'Space Grotesk'", fontWeight:600, fontSize:15, marginBottom:14 }}>دارایی‌های شما</div>
              {holdings.length === 0 ? (
                <div style={{ fontSize:13, color:'var(--faint)' }}>دارایی‌ای یافت نشد</div>
              ) : holdings.map(h => (
                <div key={h.currency} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'9px 0', borderBottom:'1px solid var(--border)' }}>
                  <span style={{ fontWeight:600, fontFamily:"'JetBrains Mono'" }}>{h.currency==='RLS'?'تومان':h.currency}</span>
                  <span style={{ textAlign:'end' }}>
                    <div style={{ fontFamily:"'JetBrains Mono'", fontSize:13 }}>{h.currency==='RLS' ? '' : h.amount.toLocaleString(undefined,{maximumFractionDigits:8})}</div>
                    <div style={{ fontFamily:"'JetBrains Mono'", fontSize:12, color:'var(--dim)' }}>{h.value_toman.toLocaleString(undefined,{maximumFractionDigits:0})} تومان</div>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
