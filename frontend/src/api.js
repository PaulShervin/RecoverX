const BASE = '/api'

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  health: () => req('/health'),
  summary: () => req('/analytics/summary'),
  byCaseType: () => req('/analytics/by-case-type'),
  byAction: () => req('/analytics/by-action'),
  cases: (status, skip = 0, limit = 100) => {
    const q = new URLSearchParams({ skip, limit })
    if (status) q.set('status', status)
    return req(`/cases/?${q}`)
  },
  getCase: id => req(`/cases/${id}`),
  detect: () => req('/cases/detect', { method: 'POST' }),
  processAll: () => req('/cases/process-all', { method: 'POST' }),
  processOne: id => req(`/cases/${id}/process`, { method: 'POST' }),
  simulateRecovered: (id, paymentId = 'pay_demo') =>
    req(`/cases/${id}/simulate-recovered?payment_id=${paymentId}`, { method: 'POST' }),
  simulateFailed: (id, reason = 'demo_failure') =>
    req(`/cases/${id}/simulate-failed?reason=${reason}`, { method: 'POST' }),
  seed: (count = 300) =>
    req('/data/seed', { method: 'POST', body: JSON.stringify({ count, seed: 42 }) }),
  reset: () => req('/data/reset', { method: 'DELETE' }),
  resolveCase: (id, resolution) =>
    req(`/cases/${id}/resolve?resolution=${resolution}`, { method: 'POST' }),
  createOrder: (amount, receipt, case_id = null) =>
    req('/payments/create-order', { method: 'POST', body: JSON.stringify({ amount, currency: 'INR', receipt, case_id }) }),
  verifyPayment: (razorpay_order_id, razorpay_payment_id, razorpay_signature, case_id = null) =>
    req('/payments/verify', { method: 'POST', body: JSON.stringify({ razorpay_order_id, razorpay_payment_id, razorpay_signature, case_id }) }),
  getOutreach: id => req(`/cases/${id}/outreach`),
  promiseToPay: (id, promise_date, note = '') =>
    req(`/cases/${id}/promise-to-pay`, { method: 'POST', body: JSON.stringify({ promise_date, note }) }),
  simulateBatchOutcomes: () => req('/cases/simulate-batch-outcomes', { method: 'POST' }),
}
