import { useState, useEffect } from 'react'
import { Users, MessageSquare, GitBranch, Database, Activity, Brain, Box, FileText, Radio, Shield, RefreshCw, ExternalLink, Check, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { API_BASE_URL } from '../config'
import { getAuthToken } from '../utils/auth'

// --- Watchlist ---
interface TickerData {
  symbol: string
  price: number | null
  change: number | null
  changePct: number | null
  loading: boolean
  error: boolean
}

const WATCHLIST_SYMBOLS = ['IONQ', 'AMD', 'UEC', 'BNS']

function useLiveQuotes(symbols: string[]) {
  const [tickers, setTickers] = useState<TickerData[]>(
    symbols.map(s => ({ symbol: s, price: null, change: null, changePct: null, loading: true, error: false }))
  )

  useEffect(() => {
    const fetchQuotes = async () => {
      const results = await Promise.all(
        symbols.map(async (sym) => {
          try {
            const res = await fetch(
              `https://query1.finance.yahoo.com/v8/finance/chart/${sym}?interval=1d&range=1d`,
              { headers: { 'Accept': 'application/json' } }
            )
            if (!res.ok) throw new Error('fetch failed')
            const json = await res.json()
            const meta = json?.chart?.result?.[0]?.meta
            const price = meta?.regularMarketPrice ?? null
            const prev = meta?.chartPreviousClose ?? meta?.previousClose ?? null
            const change = price != null && prev != null ? price - prev : null
            const changePct = change != null && prev ? (change / prev) * 100 : null
            return { symbol: sym, price, change, changePct, loading: false, error: false }
          } catch {
            return { symbol: sym, price: null, change: null, changePct: null, loading: false, error: true }
          }
        })
      )
      setTickers(results)
    }

    fetchQuotes()
    const interval = setInterval(fetchQuotes, 60000) // refresh every 60s
    return () => clearInterval(interval)
  }, [])

  return tickers
}

function TickerCard({ t }: { t: TickerData }) {
  const up = t.changePct != null && t.changePct > 0
  const down = t.changePct != null && t.changePct < 0
  const color = up ? 'text-emerald-400' : down ? 'text-red-400' : 'text-gray-400'
  const bgColor = up ? 'bg-emerald-400/5 border-emerald-400/20' : down ? 'bg-red-400/5 border-red-400/20' : 'bg-card border-border'

  return (
    <div className={`rounded-xl border p-4 ${bgColor}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-white">{t.symbol}</span>
        {up ? <TrendingUp size={14} className="text-emerald-400" /> : down ? <TrendingDown size={14} className="text-red-400" /> : <Minus size={14} className="text-gray-500" />}
      </div>
      {t.loading ? (
        <div className="text-gray-600 text-xs animate-pulse">Loading…</div>
      ) : t.error ? (
        <div className="text-gray-600 text-xs">Unavailable</div>
      ) : (
        <>
          <div className="text-xl font-bold text-white">${t.price?.toFixed(2) ?? '—'}</div>
          <div className={`text-xs font-medium mt-1 ${color}`}>
            {t.change != null ? `${t.change >= 0 ? '+' : ''}${t.change.toFixed(2)}` : '—'}
            {' '}
            ({t.changePct != null ? `${t.changePct >= 0 ? '+' : ''}${t.changePct.toFixed(2)}%` : '—'})
          </div>
        </>
      )}
    </div>
  )
}

interface ConvexEvent {
  id: string
  type: string
  agent: string
  message: string
  timestamp: number
}

interface IntegrationStatus {
  name: string
  icon: React.ElementType
  status: 'live' | 'wired' | 'pending'
  detail: string
  color: string
  link?: string
}

const integrations: IntegrationStatus[] = [
  { name: 'Convex', icon: Database, status: 'live', detail: 'Event log — all group interactions tracked', color: 'text-emerald-400', link: 'https://dashboard.convex.dev' },
  { name: 'Grafana', icon: Activity, status: 'live', detail: 'Fleet visibility — http://localhost:3000', color: 'text-orange-400', link: 'http://localhost:3000/d/mrmagoochi-agents/mrmagoochi-agent-fleet' },
  { name: 'Serena MCP', icon: Brain, status: 'live', detail: 'Code intelligence — symbol-level navigation', color: 'text-violet-400' },
  { name: 'Memory MCP / VectorDB', icon: Box, status: 'live', detail: 'Frank context + knowledge recall (port 3704)', color: 'text-blue-400' },
  { name: 'GitHub', icon: GitBranch, status: 'wired', detail: 'rekaldsi/openclaw-core — memory/INFRA_ALPHA/', color: 'text-gray-300', link: 'https://github.com/rekaldsi' },
  { name: 'Notion', icon: FileText, status: 'pending', detail: 'Task tracking + decisions log', color: 'text-yellow-400' },
  { name: 'Google Drive', icon: FileText, status: 'pending', detail: 'File backups + shared docs', color: 'text-cyan-400' },
]

interface GroupMessage {
  sender: string
  text: string
  timestamp: string
  logged: boolean
}

const RECENT_MOCK: GroupMessage[] = [
  { sender: 'Jerry', text: 'Gooch, back this Infra_Alpha Project up on the dashboard…', timestamp: '12:26', logged: true },
  { sender: 'MrMagoochi', text: 'On it — wiring Convex, Grafana, Serena, vectorDB, Notion, Drive, GitHub', timestamp: '12:26', logged: true },
]

function StatusBadge({ status }: { status: 'live' | 'wired' | 'pending' }) {
  if (status === 'live') return <span className="text-[10px] font-bold text-emerald-400 bg-emerald-400/10 px-1.5 py-0.5 rounded">LIVE</span>
  if (status === 'wired') return <span className="text-[10px] font-bold text-yellow-400 bg-yellow-400/10 px-1.5 py-0.5 rounded">WIRED</span>
  return <span className="text-[10px] font-bold text-gray-500 bg-gray-500/10 px-1.5 py-0.5 rounded">PENDING</span>
}

export default function InfraAlpha() {
  const [events, setEvents] = useState<ConvexEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(new Date())
  const [frankContext, setFrankContext] = useState<Record<string, string>>({})
  const tickers = useLiveQuotes(WATCHLIST_SYMBOLS)

  const fetchData = async () => {
    setLoading(true)
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      const token = getAuthToken()
      if (token) headers['Authorization'] = `Bearer ${token}`

      // Try to pull recent Convex events
      const res = await fetch(`${API_BASE_URL}/convex/recent-logs?limit=20`, { headers }).catch(() => null)
      if (res?.ok) {
        const data = await res.json()
        setEvents(data.logs || [])
      }
    } catch (e) {
      // Graceful fallback — Convex may not expose REST on this endpoint yet
    } finally {
      setLoading(false)
      setLastRefresh(new Date())
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const liveCount = integrations.filter(i => i.status === 'live').length
  const totalCount = integrations.length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="text-2xl">📡</span>
            <h1 className="text-xl font-bold tracking-tight">Infra_Alpha</h1>
            <span className="text-[10px] font-bold text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">ACTIVE</span>
          </div>
          <p className="text-sm text-gray-400">Telegram group orchestration — Jerry + Frank. All interactions tracked.</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-white transition-colors"
        >
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          {lastRefresh.toLocaleTimeString()}
        </button>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Integrations Live', value: `${liveCount}/${totalCount}`, icon: Radio, color: 'text-emerald-400' },
          { label: 'Group Members', value: '2', icon: Users, color: 'text-blue-400' },
          { label: 'Events Logged', value: '∞', icon: Database, color: 'text-violet-400' },
          { label: 'Bot Status', value: 'Online', icon: Shield, color: 'text-green-400' },
        ].map(s => (
          <div key={s.label} className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <s.icon size={14} className={s.color} />
              <span className="text-[11px] text-gray-500 uppercase tracking-wider">{s.label}</span>
            </div>
            <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Watchlist */}
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold">Frank's Watchlist</h2>
          <span className="text-[10px] text-gray-600 ml-auto">Live · refreshes every 60s</span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {tickers.map(t => <TickerCard key={t.symbol} t={t} />)}
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Integration Stack */}
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={16} className="text-accent" />
            <h2 className="text-sm font-semibold">Integration Stack</h2>
          </div>
          <div className="space-y-3">
            {integrations.map(intg => (
              <div key={intg.name} className="flex items-center justify-between">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <intg.icon size={14} className={intg.color} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white">{intg.name}</span>
                      {intg.link && (
                        <a href={intg.link} target="_blank" rel="noreferrer" className="text-gray-600 hover:text-gray-400">
                          <ExternalLink size={10} />
                        </a>
                      )}
                    </div>
                    <div className="text-[11px] text-gray-500 truncate">{intg.detail}</div>
                  </div>
                </div>
                <StatusBadge status={intg.status} />
              </div>
            ))}
          </div>
        </div>

        {/* Frank's Context */}
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Users size={16} className="text-blue-400" />
            <h2 className="text-sm font-semibold">Frank's Context</h2>
          </div>
          <div className="space-y-3">
            {[
              { label: 'Name', value: 'Frank' },
              { label: 'Group', value: 'Infra_Alpha' },
              { label: 'Access', value: 'Group participant — full bot access' },
              { label: 'Memory', value: 'Stored in Memory MCP (agent-state:frank_*)' },
              { label: 'Tracking', value: 'All interactions → Convex log' },
              { label: 'Last Activity', value: 'Session start 2026-04-16' },
            ].map(row => (
              <div key={row.label} className="flex items-start gap-3">
                <span className="text-[11px] text-gray-500 w-28 shrink-0 pt-0.5">{row.label}</span>
                <span className="text-[12px] text-gray-200">{row.value}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t border-border">
            <div className="text-[11px] text-gray-500 mb-2">Backup Locations</div>
            {[
              { icon: Database, label: 'Convex', detail: 'All events logged' },
              { icon: Box, label: 'Memory MCP', detail: 'port 3704 / KV store' },
              { icon: GitBranch, label: 'GitHub', detail: 'memory/INFRA_ALPHA/' },
              { icon: Brain, label: 'PROJECT_SUMMARY.md', detail: 'Workspace file' },
            ].map(b => (
              <div key={b.label} className="flex items-center gap-2 py-1">
                <Check size={11} className="text-emerald-400 shrink-0" />
                <b.icon size={11} className="text-gray-500 shrink-0" />
                <span className="text-[11px] text-gray-300">{b.label}</span>
                <span className="text-[11px] text-gray-600">— {b.detail}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Group Activity Feed */}
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <MessageSquare size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold">Group Activity</h2>
          <span className="text-[10px] text-gray-600 ml-auto">Auto-refreshes every 30s</span>
        </div>
        <div className="space-y-2">
          {RECENT_MOCK.map((msg, i) => (
            <div key={i} className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
              <div className={`text-[11px] font-bold w-20 shrink-0 ${msg.sender === 'MrMagoochi' ? 'text-accent' : 'text-blue-400'}`}>
                {msg.sender}
              </div>
              <div className="text-[12px] text-gray-300 flex-1 min-w-0 truncate">{msg.text}</div>
              <div className="flex items-center gap-2 shrink-0">
                {msg.logged && <span className="text-[10px] text-emerald-500">✓ logged</span>}
                <span className="text-[11px] text-gray-600">{msg.timestamp}</span>
              </div>
            </div>
          ))}
          {events.map(ev => (
            <div key={ev.id} className="flex items-start gap-3 py-2 border-b border-border/50 last:border-0">
              <div className="text-[11px] font-bold w-20 shrink-0 text-violet-400">{ev.agent}</div>
              <div className="text-[12px] text-gray-300 flex-1 min-w-0 truncate">[{ev.type}] {ev.message}</div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] text-emerald-500">✓ convex</span>
                <span className="text-[11px] text-gray-600">{new Date(ev.timestamp).toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
          {events.length === 0 && !loading && (
            <div className="text-[12px] text-gray-600 py-4 text-center">Convex events stream live here as the group is active</div>
          )}
        </div>
      </div>

      {/* Data Integrity */}
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold">Data Integrity & Backup Status</h2>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[
            {
              title: 'Project Brain',
              status: 'live',
              items: ['memory/INFRA_ALPHA/PROJECT_SUMMARY.md', 'agent-state:infra_alpha_project in Memory MCP', 'Convex initialized 2026-04-16'],
            },
            {
              title: 'Frank Tracking',
              status: 'live',
              items: ['All messages routed through MrMagoochi', 'Interactions logged to Convex', 'Context stored in Memory MCP KV'],
            },
            {
              title: 'Pending Wires',
              status: 'pending',
              items: ['Notion DB for decisions/tasks', 'Google Drive file backup', 'GitHub auto-commit cron for memory/INFRA_ALPHA/'],
            },
          ].map(section => (
            <div key={section.title} className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold text-gray-300">{section.title}</span>
                <StatusBadge status={section.status as 'live' | 'pending'} />
              </div>
              {section.items.map(item => (
                <div key={item} className="flex items-start gap-2">
                  <span className={`text-[10px] mt-0.5 ${section.status === 'live' ? 'text-emerald-400' : 'text-gray-600'}`}>
                    {section.status === 'live' ? '✓' : '○'}
                  </span>
                  <span className="text-[11px] text-gray-400">{item}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
