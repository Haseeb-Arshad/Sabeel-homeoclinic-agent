# Sabeel Homeo Clinic Chatbot - Manual Testing Guide

This guide describes how to run the backend locally and test its supported channels.

## 1. Local Environment Setup

### Prerequisites
- Python 3.11 or 3.12 recommended
- FFmpeg installed and added to PATH
- Ngrok installed
- `.env` file populated with the provider keys for the channels you want to test

### Start the Server
Open a terminal in the project root and run:

```powershell
uvicorn main:app --reload --port 8000
```

You should see `Uvicorn running on http://127.0.0.1:8000`.

### Verify Basic Health
Open:

```text
http://127.0.0.1:8000/health
```

Expected shape:

```json
{
  "status": "healthy",
  "service": "Sabeel Homeo Clinic AI Chatbot",
  "version": "1.1.0",
  "channels": {
    "openai": true,
    "twilio": true,
    "deepgram": true,
    "elevenlabs": true,
    "meta": false,
    "evolution": false
  }
}
```

### Start Ngrok
Open a second terminal and run:

```powershell
ngrok http 8000
```

Copy the forwarding URL, for example `https://your-ngrok-id.ngrok-free.app`.

## 2. Web Chat Testing

### JSON Chat Endpoint

```powershell
curl -X POST http://127.0.0.1:8000/api/chat `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"What are your timings?\"}"
```

### SSE Streaming Endpoint

```powershell
curl -N -X POST http://127.0.0.1:8000/api/chat/stream `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"Where is the clinic located?\"}"
```

## 3. Twilio Configuration

### Voice
Set your Twilio number voice webhook to:

```text
https://<your-ngrok-url>/twilio/voice/incoming
```

Twilio will call this HTTP route, receive TwiML, and then connect the call to:

```text
wss://<your-ngrok-url>/ws/media-stream
```

### WhatsApp
Set Twilio WhatsApp incoming messages to:

```text
https://<your-ngrok-url>/webhook/whatsapp
```

Method: `POST`

### Twilio Test Scenarios
1. Send a text message to the Twilio WhatsApp number and confirm the reply is generated.
2. Send a voice note and confirm transcription plus audio or text reply.
3. Call the Twilio number and confirm the media stream connects.

## 4. Meta Configuration

In the Meta Developers portal, set the webhook callback URL to:

```text
https://<your-ngrok-url>/webhook/meta
```

Use the value of `META_VERIFY_TOKEN` from `.env` as the verify token.

### Meta Test Scenarios
1. Verify the webhook successfully in the Meta dashboard.
2. Send a text message on Messenger or Instagram DM and confirm the bot replies.

## 5. Evolution API Configuration

### Start Evolution API

```powershell
docker compose up -d
```

### Configure Webhook
Point Evolution's instance webhook to:

```text
https://<your-ngrok-url>/webhook/evolution
```

Recommended Evolution settings:
- `webhook_by_events=false`
- `webhook_base64=true` if you want media embedded directly in the webhook
- Or configure S3/Minio so the webhook includes `message.mediaUrl`

### Evolution Test Scenarios
1. Send a text message and confirm a text reply is sent back through Evolution.
2. Send a voice note and confirm one of these paths works:
   - `message.mediaUrl` is present in the webhook
   - inline base64 media is present in the webhook
   - Evolution can serve media through `POST /chat/getBase64FromMediaMessage/{instance}`

## 6. Knowledge Base and Supabase

If you want persistence plus website-grounded responses:

1. Create a Supabase project.
2. Run the SQL in `database/schema.sql`.
3. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in `.env`.
4. Ingest website data:

```powershell
venv\Scripts\python.exe scripts\ingest_wordpress_kb.py
```

## 7. Automated Checks

Run the built-in sanity check:

```powershell
venv\Scripts\python.exe check_env.py
```

Run the test suite:

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -v
```
