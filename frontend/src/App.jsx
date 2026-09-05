import { useState, useEffect, useCallback } from 'react'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { api } from './api.js'
import StatCard from './components/StatCard.jsx'
import CaseList from './components/CaseList.jsx'
import CaseDetail from './components/CaseDetail.jsx'

const COLORS = ['#22c55e', '#ef4444', '#8b5cf6', '#f59e0b']

export default function App() {
  const [summary, setSummary] = useState(null)
  const [cases, setCases] = useState([])
  const [byType, setByType] = useState({})
  const [byAction, setByAction] = useState([])
  const [selectedCase, setSelectedCase] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [casesLimit, setCasesLimit] = useState(100)
  const [loading, setLoading] = useState(false)
  const [log, setLog] = useState([])

  const addLog = msg => setLog(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 20))

  const refresh = useCallback(async () => {
    const [s, c, t, a] = await Promise.all([
      api.summary().catch(() => null),
      api.cases(statusFilter, 0, casesLimit).catch(() => []),
      api.byCaseType().catch(() => ({})),
      api.byAction().catch(() => []),
    ])
    setSummary(s)
    setCases(c)
    setByType(t)
    setByAction(a)
  }, [statusFilter, casesLimit])

  useEffect(() => { refresh() }, [refresh])

  const run = async (fn, label) => {
    setLoading(true)
    addLog(`${label}…`)
    try {
      const r = await fn()
      addLog(`✓ ${label}: ${JSON.stringify(r).slice(0, 120)}`)
    } catch (e) {
      addLog(`✗ ${label}: ${e.message}`)
    } finally {
      setLoading(false)
      refresh()
    }
  }

  const statusCounts = summary ? [
    { name: 'Recovered', value: summary.recovered_cases },
    { name: 'Failed', value: summary.failed_cases },
    { name: 'Escalated', value: summary.escalated_cases },
    { name: 'Promised', value: summary.promised_cases || 0 },
    { name: 'Open', value: summary.open_cases },
  ] : []

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '24px 20px' }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: -0.5 }}>
          <span style={{ color: '#6366f1' }}>RecoverX</span> — AI Revenue Recovery Agent
        </h1>
        <p style={{ color: '#64748b', fontSize: 13, marginTop: 4 }}>Razorpay Buildathon · Track 03</p>
      </div>

      {/* Action bar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        {[
          { label: '⚡ Seed 300 Records', fn: () => api.seed(300), color: '#374151' },
          { label: '🔍 Detect Cases', fn: api.detect, color: '#374151' },
          { label: '▶ Process All Open', fn: api.processAll, color: '#6366f1' },
          { label: '🎯 Simulate Batch Recoveries', fn: api.simulateBatchOutcomes, color: '#059669' },
          { label: '↺ Refresh', fn: () => Promise.resolve(refresh()), color: '#374151' },
          { label: '🗑 Reset All', fn: api.reset, color: '#7f1d1d' },
        ].map(({ label, fn, color }) => (
          <button
            key={label}
            onClick={() => run(fn, label)}
            disabled={loading}
            style={{ background: color, color: '#fff', border: 'none', borderRadius: 8, padding: '8px 16px', cursor: 'pointer', fontWeight: 600, fontSize: 13 }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* KPI row */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 16, marginBottom: 28 }}>
          <StatCard label="Revenue at Risk" value={`₹${(summary.total_revenue_at_risk / 1000).toFixed(0)}K`} accent="#ef4444" />
          <StatCard label="Revenue Recovered" value={`₹${(summary.total_revenue_recovered / 1000).toFixed(0)}K`} accent="#22c55e" />
          <StatCard label="Recovery Rate" value={`${summary.recovery_rate.toFixed(1)}%`} accent="#6366f1" />
          <StatCard label="Penalties Saved" value={`₹${(summary.gateway_penalties_prevented || 0).toLocaleString('en-IN')}`} sub="Stopping rule ROI" accent="#10b981" />
          <StatCard label="Total Cases" value={summary.total_cases} sub={`${summary.open_cases} open`} accent="#f59e0b" />
          <StatCard label="Promised to Pay" value={summary.promised_cases || 0} sub="P2P Snoozed" accent="#06b6d4" />
          <StatCard label="Escalated" value={summary.escalated_cases} accent="#8b5cf6" />
          <StatCard label="Avg Recovery Time" value={summary.avg_recovery_time_seconds != null ? `${summary.avg_recovery_time_seconds.toFixed(0)}s` : '—'} accent="#a855f7" />
        </div>
      )}

      {/* Charts */}
      {summary && summary.total_cases > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
          <div style={{ background: '#1a1f2e', borderRadius: 12, padding: 20 }}>
            <h3 style={{ fontSize: 14, color: '#94a3b8', marginBottom: 16 }}>Case Outcomes</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                {(() => {
                  const filtered = statusCounts.filter(d => d.value > 0)
                  return (
                    <Pie data={filtered} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                      {filtered.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                  )
                })()}
                <Tooltip formatter={(v) => v} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ background: '#1a1f2e', borderRadius: 12, padding: 20 }}>
            <h3 style={{ fontSize: 14, color: '#94a3b8', marginBottom: 16 }}>Actions Taken</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={byAction.slice(0, 8)} layout="vertical">
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis dataKey="action" type="category" width={160} tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={v => v.replace(/_/g, ' ')} />
                <Tooltip formatter={(v) => v} />
                <Bar dataKey="count" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Cases table */}
      <div style={{ background: '#1a1f2e', borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700 }}>Cases ({cases.length})</h3>
          <select
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setCasesLimit(100) }}
            style={{ background: '#0f1117', color: '#94a3b8', border: '1px solid #374151', borderRadius: 6, padding: '4px 10px', fontSize: 13 }}
          >
            <option value="">All statuses</option>
            {['OPEN', 'RECOVERED', 'FAILED', 'ESCALATED', 'PROMISED_TO_PAY'].map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </select>
        </div>
        <CaseList cases={cases} onSelect={setSelectedCase} />
        {cases.length === casesLimit && (
          <div style={{ textAlign: 'center', paddingTop: 12 }}>
            <button
              onClick={() => setCasesLimit(l => l + 100)}
              style={{ background: '#1e293b', color: '#94a3b8', border: '1px solid #334155', borderRadius: 8, padding: '6px 20px', cursor: 'pointer', fontSize: 13 }}
            >
              Load More ({casesLimit} shown)
            </button>
          </div>
        )}
      </div>

      {/* Activity log */}
      {log.length > 0 && (
        <div style={{ background: '#0a0f1a', borderRadius: 8, padding: 16, fontFamily: 'monospace', fontSize: 12 }}>
          <div style={{ color: '#475569', marginBottom: 8, fontSize: 11, textTransform: 'uppercase' }}>Activity Log</div>
          {log.map((l, i) => (
            <div key={i} style={{ color: l.includes('✗') ? '#ef4444' : l.includes('✓') ? '#22c55e' : '#94a3b8', padding: '2px 0' }}>{l}</div>
          ))}
        </div>
      )}

      {selectedCase && <CaseDetail caseId={selectedCase} onClose={() => { setSelectedCase(null); refresh() }} />}
    </div>
  )
}
