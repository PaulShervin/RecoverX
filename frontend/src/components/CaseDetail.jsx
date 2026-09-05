import { useState, useEffect } from 'react'
import { api } from '../api.js'
import AuditTrail from './AuditTrail.jsx'

const RZP_KEY = import.meta.env.VITE_RAZORPAY_KEY_ID

const STATUS_COLORS = {
  OPEN: '#f59e0b', RECOVERED: '#22c55e', FAILED: '#ef4444', ESCALATED: '#8b5cf6', PROMISED_TO_PAY: '#06b6d4',
}

export default function CaseDetail({ caseId, onClose }) {
  const [c, setC] = useState(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [outreach, setOutreach] = useState(null)
  const [activeTab, setActiveTab] = useState(0)
  const [p2pDate, setP2pDate] = useState('')
  const [p2pNote, setP2pNote] = useState('')
  const [showP2p, setShowP2p] = useState(false)
  const [copied, setCopied] = useState(false)

  const load = () => {
    setLoading(true)
    api.getCase(caseId).then(data => {
      setC(data)
      api.getOutreach(caseId).then(setOutreach).catch(() => {})
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [caseId])

  const process = async () => {
    setActing(true)
    await api.processOne(caseId).catch(() => {})
    load()
    setActing(false)
  }

  const handlePromiseToPay = async () => {
    if (!p2pDate) {
      alert('Please select a promise-to-pay date')
      return
    }
    setActing(true)
    try {
      await api.promiseToPay(caseId, new Date(p2pDate).toISOString(), p2pNote)
      setShowP2p(false)
      load()
    } catch (err) {
      alert(`Failed to record P2P: ${err.message}`)
    } finally {
      setActing(false)
    }
  }

  const simRecover = async () => {
    setActing(true)
    await api.simulateRecovered(caseId).catch(() => {})
    load()
    setActing(false)
  }

  const resolve = async (resolution) => {
    setActing(true)
    await api.resolveCase(caseId, resolution).catch(() => {})
    load()
    setActing(false)
  }

  const payNow = async () => {
    if (typeof window.Razorpay === 'undefined') {
      alert('Razorpay checkout did not load. Disable ad-blockers and refresh.')
      return
    }
    setActing(true)
    try {
      const amountPaise = Math.round((c.amount || 100) * 100)
      const order = await api.createOrder(amountPaise, c.case_id.slice(0, 40), c.case_id)
      const options = {
        key: RZP_KEY,
        amount: order.amount,
        currency: 'INR',
        order_id: order.order_id,
        name: 'RecoverX',
        description: `Payment Recovery — Case ${c.case_id.slice(0, 8)}`,
        theme: { color: '#6366f1' },
        prefill: {
          name: c.customer_name || 'Rahul Sharma',
          email: 'customer@recoverx.demo',
          contact: '9876543210',
          method: 'upi',
        },
        notes: {
          test_hint: "UPI: success@razorpay (OTP 123456) | Card: 4111 1111 1111 1111, any future date, CVV 123",
        },
        handler: async ({ razorpay_payment_id, razorpay_order_id, razorpay_signature }) => {
          try {
            await api.verifyPayment(razorpay_order_id, razorpay_payment_id, razorpay_signature, c.case_id)
            load()
          } catch (err) {
            alert(`Verification failed: ${err.message}`)
          } finally {
            setActing(false)
          }
        },
        modal: {
          ondismiss: () => setActing(false),
        },
      }
      const rzp = new window.Razorpay(options)
      rzp.on('payment.failed', ({ error }) => {
        alert(`Payment failed: ${error.description}`)
        setActing(false)
      })
      // Show test-mode credentials before opening checkout
      // eslint-disable-next-line no-console
      console.info('[RecoverX Test Mode] UPI: success@razorpay OTP: 123456 | Card: 4111 1111 1111 1111 exp: any future date CVV: 123')
      rzp.open()
    } catch (err) {
      alert(`Could not open checkout: ${err.message}`)
      setActing(false)
    }
  }

  if (loading) return <Overlay><p style={{ color: '#94a3b8' }}>Loading…</p></Overlay>
  if (!c) return null

  const pct = c.recovery_probability != null ? `${(c.recovery_probability * 100).toFixed(0)}%` : '—'

  return (
    <Overlay>
      <div style={{ background: '#1a1f2e', borderRadius: 16, padding: 32, maxWidth: 760, width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div>
            <h2 style={{ fontSize: 20, marginBottom: 4 }}>Case {c.case_id.slice(0, 8)}…</h2>
            <span style={{ background: STATUS_COLORS[c.status] + '22', color: STATUS_COLORS[c.status], padding: '2px 10px', borderRadius: 20, fontSize: 12, fontWeight: 700 }}>
              {c.status}
            </span>
          </div>
          <button onClick={onClose} style={btnStyle('#374151')}>✕ Close</button>
        </div>

        <Grid>
          <Field label="Amount" value={`₹${c.amount?.toLocaleString('en-IN')}`} />
          <Field label="Case Type" value={c.case_type} />
          <Field label="Failure Reason" value={c.failure_reason || '—'} />
          <Field label="Retry Count" value={c.retry_count} />
          <Field label="Recovery Probability" value={pct} />
          <Field label="Approved Action" value={c.approved_action || '—'} />
        </Grid>

        {c.diagnosis && (
          <Section title="AI Diagnosis">
            <p style={{ color: '#cbd5e1', lineHeight: 1.6 }}>{c.diagnosis}</p>
            {c.reasoning && <p style={{ color: '#64748b', fontSize: 12, marginTop: 8 }}>{c.reasoning}</p>}
          </Section>
        )}

        {c.payment_link_url && (
          <div style={{ background: '#05966918', border: '1px solid #10b981', borderRadius: 10, padding: 14, marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
              <div>
                <span style={{ color: '#34d399', fontWeight: 700, fontSize: 13 }}>⚡ Razorpay UPI Fast-Pay Link Generated</span>
                <p style={{ color: '#94a3b8', fontSize: 12, margin: '4px 0 0 0' }}>Fallback routing active: Bypasses failed card directly via UPI / QR</p>
              </div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(c.payment_link_url)
                  setCopied(true)
                  setTimeout(() => setCopied(false), 2000)
                }}
                style={btnStyle('#059669')}
              >
                {copied ? '✓ Copied Link' : '📋 Copy UPI Link'}
              </button>
            </div>
          </div>
        )}

        {c.status === 'PROMISED_TO_PAY' && (
          <div style={{ background: '#0891b218', border: '1px solid #06b6d4', borderRadius: 10, padding: 14, marginBottom: 16 }}>
            <span style={{ color: '#22d3ee', fontWeight: 700, fontSize: 13 }}>🤝 Promise-to-Pay Active (Snoozed)</span>
            <p style={{ color: '#cbd5e1', fontSize: 13, margin: '4px 0 0 0' }}>
              Customer committed to pay by <strong>{c.promise_date ? new Date(c.promise_date).toLocaleDateString() : 'committed date'}</strong>. Automated retries are paused.
            </p>
            {c.promise_note && <p style={{ color: '#94a3b8', fontSize: 12, marginTop: 4 }}>Note: {c.promise_note}</p>}
          </div>
        )}

        {c.guardrail_override && (
          <div style={{ background: '#f59e0b11', border: '1px solid #f59e0b44', borderRadius: 8, padding: 12, marginBottom: 16 }}>
            <span style={{ color: '#f59e0b', fontWeight: 700 }}>⚠ Guardrail override: </span>
            <span style={{ color: '#fcd34d', fontSize: 13 }}>{c.guardrail_reason}</span>
          </div>
        )}

        {outreach && outreach.messages && outreach.messages.length > 0 && (
          <Section title="Multi-Channel Recovery Outreach (Hinglish & Localized)">
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              {outreach.messages.map((m, idx) => (
                <button
                  key={m.channel}
                  onClick={() => setActiveTab(idx)}
                  style={{
                    background: activeTab === idx ? '#4f46e5' : '#1e293b',
                    color: activeTab === idx ? '#fff' : '#94a3b8',
                    border: '1px solid ' + (activeTab === idx ? '#6366f1' : '#334155'),
                    borderRadius: 6,
                    padding: '6px 12px',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <div style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, padding: 14 }}>
              <pre style={{ color: '#e2e8f0', fontSize: 12, whiteSpace: 'pre-wrap', fontFamily: 'inherit', margin: 0, lineHeight: 1.5 }}>
                {outreach.messages[activeTab]?.content}
              </pre>
              <div style={{ marginTop: 10, display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(outreach.messages[activeTab]?.content || '')
                    alert('Outreach copy copied to clipboard!')
                  }}
                  style={{ ...btnStyle('#334155'), fontSize: 11, padding: '4px 10px' }}
                >
                  📋 Copy Message
                </button>
              </div>
            </div>
          </Section>
        )}

        <Section title="Audit Trail">
          <AuditTrail events={c.audit_events} />
        </Section>

        {showP2p && (
          <div style={{ background: '#0f172a', border: '1px solid #38bdf8', borderRadius: 10, padding: 16, marginTop: 16 }}>
            <h4 style={{ color: '#38bdf8', margin: '0 0 10px 0', fontSize: 13 }}>Record Customer Promise-to-Pay</h4>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
              <input
                type="date"
                value={p2pDate}
                onChange={e => setP2pDate(e.target.value)}
                style={{ background: '#1e293b', border: '1px solid #475569', color: '#fff', padding: '6px 10px', borderRadius: 6, fontSize: 13 }}
              />
              <input
                type="text"
                placeholder="Optional customer note (e.g. Salary on Friday)"
                value={p2pNote}
                onChange={e => setP2pNote(e.target.value)}
                style={{ flex: 1, minWidth: 200, background: '#1e293b', border: '1px solid #475569', color: '#fff', padding: '6px 10px', borderRadius: 6, fontSize: 13 }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handlePromiseToPay} disabled={acting} style={btnStyle('#0284c7')}>
                {acting ? 'Saving…' : '✓ Confirm Promise & Snooze'}
              </button>
              <button onClick={() => setShowP2p(false)} style={btnStyle('#334155')}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {(c.status === 'OPEN' || c.status === 'ESCALATED') && (
          <div style={{ display: 'flex', gap: 12, marginTop: 20, flexWrap: 'wrap' }}>
            {c.status === 'OPEN' && (
              <>
                <button onClick={process} disabled={acting} style={btnStyle('#6366f1')}>
                  {acting ? 'Processing…' : '▶ Run Pipeline'}
                </button>
                <button onClick={payNow} disabled={acting} style={btnStyle('#0f9d58')}>
                  {acting ? 'Opening…' : `💳 Pay Now ₹${c.amount?.toLocaleString('en-IN')}`}
                </button>
                <button onClick={simRecover} disabled={acting} style={btnStyle('#22c55e')}>
                  ✓ Simulate Recovered
                </button>
              </>
            )}
            {c.status === 'ESCALATED' && (
              <>
                <button onClick={() => resolve('recovered')} disabled={acting} style={btnStyle('#22c55e')}>
                  {acting ? 'Saving…' : '✓ Approve Manual Recovery'}
                </button>
                <button onClick={() => resolve('dismissed')} disabled={acting} style={btnStyle('#ef4444')}>
                  {acting ? 'Saving…' : '✗ Dismiss Case'}
                </button>
              </>
            )}
            {!showP2p && (
              <button onClick={() => setShowP2p(true)} style={btnStyle('#0284c7')}>
                🤝 Promise-to-Pay
              </button>
            )}
            {c.status === 'OPEN' && (
              <div style={{ width: '100%', marginTop: 8 }}>
                <span style={{ color: '#94a3b8', fontSize: 11 }}>
                  💡 <strong>Test Mode Tip:</strong> For instant success in Razorpay checkout, select <strong>UPI (use VPA: success@razorpay, OTP: 123456)</strong> or Card <strong>4111 1111 1111 1111</strong>.
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </Overlay>
  )
}

function Overlay({ children }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#000000aa',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: 16,
    }}>
      {children}
    </div>
  )
}

function Grid({ children }) {
  return <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>{children}</div>
}

function Field({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
      <div style={{ color: '#f1f5f9', fontWeight: 600 }}>{value ?? '—'}</div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: 14, color: '#94a3b8', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 }}>{title}</h3>
      {children}
    </div>
  )
}

function btnStyle(bg) {
  return {
    background: bg, color: '#fff', border: 'none', borderRadius: 8,
    padding: '8px 16px', cursor: 'pointer', fontWeight: 600, fontSize: 13,
  }
}
