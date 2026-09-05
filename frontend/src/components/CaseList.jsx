const STATUS_COLORS = {
  OPEN: '#f59e0b', RECOVERED: '#22c55e', FAILED: '#ef4444', ESCALATED: '#8b5cf6', PROMISED_TO_PAY: '#06b6d4',
}

export default function CaseList({ cases, onSelect }) {
  if (!cases || cases.length === 0) {
    return <p style={{ color: '#64748b', padding: 16 }}>No cases. Run detection first.</p>
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ color: '#64748b', textAlign: 'left', borderBottom: '1px solid #1e293b' }}>
            {['Case ID', 'Customer', 'Type', 'Amount', 'Failure Reason', 'Prob', 'Action', 'Status'].map(h => (
              <th key={h} style={{ padding: '10px 12px', fontWeight: 600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {cases.map(c => (
            <tr
              key={c.case_id}
              onClick={() => onSelect(c.case_id)}
              style={{ borderBottom: '1px solid #1e293b', cursor: 'pointer' }}
              onMouseEnter={e => e.currentTarget.style.background = '#1e293b'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <td style={{ padding: '10px 12px', color: '#6366f1', fontFamily: 'monospace' }}>
                {c.case_id.slice(0, 12)}…
              </td>
              <td style={{ padding: '10px 12px', color: '#e2e8f0', fontSize: 12 }}>
                {c.customer_name || '—'}
              </td>
              <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{c.case_type}</td>
              <td style={{ padding: '10px 12px', fontWeight: 600 }}>₹{c.amount?.toLocaleString('en-IN')}</td>
              <td style={{ padding: '10px 12px', color: '#94a3b8', fontSize: 12 }}>{c.failure_reason || '—'}</td>
              <td style={{ padding: '10px 12px' }}>
                {c.recovery_probability != null
                  ? <ProbBadge p={c.recovery_probability} />
                  : <span style={{ color: '#475569' }}>—</span>}
              </td>
              <td style={{ padding: '10px 12px', color: '#cbd5e1', fontSize: 12 }}>
                {c.approved_action?.replace(/_/g, ' ') || '—'}
              </td>
              <td style={{ padding: '10px 12px' }}>
                <span style={{
                  background: (STATUS_COLORS[c.status] || '#64748b') + '22',
                  color: STATUS_COLORS[c.status] || '#64748b',
                  padding: '2px 8px', borderRadius: 20, fontSize: 11, fontWeight: 700,
                }}>
                  {c.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ProbBadge({ p }) {
  const pct = (p * 100).toFixed(0)
  const color = p >= 0.6 ? '#22c55e' : p >= 0.35 ? '#f59e0b' : '#ef4444'
  return (
    <span style={{ color, fontWeight: 700 }}>{pct}%</span>
  )
}
