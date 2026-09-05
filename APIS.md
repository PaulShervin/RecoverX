# APIS — Credentials & Environment Variables

> Fill this in AFTER build is complete / when ready to connect real services.
> Never commit real keys to a public repo — use this file locally only, or
> move these into a `.env` file (gitignored) and just keep placeholders here.

---

## 1. Razorpay (Test Mode)

```
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
```

- Get keys from: Dashboard → Settings → API Keys (Test Mode)
- Webhook secret from: Dashboard → Webhooks → your endpoint
- Webhook local testing: use ngrok to expose local backend
  ```
  NGROK_PUBLIC_URL=
  ```

---

## 2. LLM — Ollama (local, chosen for this project)

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=
```

- No API key needed (runs locally)
- Model choice TBD — note it here once picked (e.g. llama3.1, mistral, qwen2.5)
- Keep the LLM call behind a single interface (e.g. `get_diagnosis()`) so swapping providers later is a one-line change

**If switching to a hosted LLM later, use this block instead:**
```
LLM_PROVIDER=
LLM_API_KEY=
LLM_MODEL=
```

---

## 3. Database

```
DATABASE_URL=
```

- e.g. local Postgres, or a hosted free tier (Supabase / Neon) connection string

---

## 4. Notifications (optional — can stay mocked for demo)

```
# Only fill in if going beyond simulated/logged notifications
EMAIL_API_KEY=
SMS_API_KEY=
```

---

## 5. Deployment (fill in if/when deployed)

```
DEPLOY_URL=
CLOUD_PROVIDER=
```

---

## Status

- [ ] Razorpay Test Mode keys added
- [ ] Webhook secret + ngrok URL added
- [ ] Ollama model finalized and noted
- [ ] Database URL added
- [ ] Notification keys added (if used)
- [ ] Deployment details added
