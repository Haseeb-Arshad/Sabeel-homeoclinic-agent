# Sabeel Homeo Clinic Chatbot - Implementation Status

## What is implemented

- FastAPI backend with channels for:
  - Twilio voice
  - Twilio WhatsApp
  - Evolution WhatsApp
  - Meta Messenger / Instagram webhooks
  - Website chat JSON and SSE endpoints
- Clinic-focused AI orchestration with:
  - clinic-only scope
  - emergency escalation behavior
  - no cure guarantee policy
  - appointment request tool calling
  - website knowledge retrieval when Supabase + embeddings are configured
- Supabase-backed persistence for:
  - `conversations`
  - `messages`
  - `appointments`
  - `kb_chunks`
- Local in-process fallback persistence when Supabase is not configured, so conversation history still works during local development
- Twilio webhook signature validation
- Evolution voice-note handling with support for:
  - direct `mediaUrl`
  - inline base64 media
  - Evolution `getBase64FromMediaMessage` fallback
- Twilio WhatsApp media retrieval with authenticated media download support

## Important fixes completed

- Fixed the Twilio WhatsApp sender bug that broke outbound sends once a sender number was configured
- Reused conversations by channel + external user ID instead of creating a brand-new thread on every inbound message
- Added recent-message history to web chat, Meta, Twilio WhatsApp, and Evolution WhatsApp flows
- Reworked config so the app can boot without every provider secret present
- Removed the startup-time `pydub` import dependency from the common runtime path
- Updated docs and setup instructions to match `uvicorn main:app`
- Expanded the automated test suite

## Setup flow

### Core app
1. Create `.env` from `.env.example`
2. Install dependencies from `requirements.txt`
3. Start the API:

```powershell
uvicorn main:app --reload
```

### Supabase
1. Create a Supabase project
2. Run `database/schema.sql`
3. Set:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`

### Knowledge ingestion

```powershell
venv\Scripts\python.exe scripts\ingest_wordpress_kb.py
```

### Validation

```powershell
venv\Scripts\python.exe check_env.py
venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Remaining production hardening

- Restrict `CORS_ALLOW_ORIGINS` for production
- Use a stable `PUBLIC_BASE_URL`
- Add external monitoring/alerting for webhook failures
- Move static audio storage to durable object storage if multiple app instances will run
- Add end-to-end provider tests against real Twilio / Meta / Evolution sandboxes before production launch
