export default function AuditTrail({ events }) {
  if (!events || events.length === 0) {
    return <p style={{ color: '#64748b', padding: 12 }}>No audit events.</p>
  }
  return (
    <div style={{ fontFamily: 'monospace', fontSize: 13 }}>
      {events.map(e => (
        <div key={e.id} style={{ display: 'flex', gap: 16, padding: '6px 0', borderBottom: '1px solid #1e293b' }}>
          <span style={{ color: '#64748b', minWidth: 200, flexShrink: 0 }}>
            {new Date(e.timestamp + 'Z').toLocaleTimeString('en-IN', { hour12: false, dateStyle: undefined })}
          </span>
          <span style={{ color: _eventColor(e.event_type), minWidth: 220, flexShrink: 0, fontWeight: 600 }}>
            {e.event_type}
          </span>
          <span style={{ color: '#cbd5e1' }}>{e.details}</span>
        </div>
      ))}
    </div>
  )
}

function _eventColor(type) {
  if (type.includes('RECOVERED') || type.includes('SUCCESS')) return '#22c55e'
  if (type.includes('FAILED') || type.includes('ERROR') || type.includes('BLOCK')) return '#ef4444'
  if (type.includes('GUARDRAIL') || type.includes('OVERRIDE')) return '#f59e0b'
  if (type.includes('WEBHOOK')) return '#8b5cf6'
  if (type.includes('DECIDED') || type.includes('APPROVED')) return '#6366f1'
  return '#94a3b8'
}
