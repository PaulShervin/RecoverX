export default function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: '#1a1f2e', borderRadius: 12, padding: '20px 24px',
      borderLeft: `4px solid ${accent || '#6366f1'}`,
    }}>
      <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: '#f1f5f9' }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}
