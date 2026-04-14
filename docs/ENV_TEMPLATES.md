# Environment Templates

Use one of the root-level example files as your starting point:

- `.env.webchat.example`
- `.env.twilio-whatsapp.example`
- `.env.fullstack.example`

## Recommended starting path

For this project, start with:

1. `webchat-only` if you want the fastest stable launch
2. `webchat + Twilio WhatsApp` if patient messaging is required now
3. `full stack` only after the first two are stable

## Minimum production recommendation

Even for web chat only, you should set:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` if you are using OpenRouter
- `OPENAI_MODEL=gpt-4o-mini`
- `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `CORS_ALLOW_ORIGINS`

## Notes

- `gpt-4o-mini` is the recommended starting model for this repo.
- If you use OpenRouter, set `OPENAI_BASE_URL=https://openrouter.ai/api/v1` and optionally set `OPENAI_HTTP_REFERER` and `OPENAI_APP_NAME`.
- Do not fine-tune first. Start with prompt + retrieval + tool calling.
- `PUBLIC_BASE_URL` is required for public webhook testing and static audio URLs.
- For Twilio voice, `DEEPGRAM_API_KEY` and `ELEVENLABS_API_KEY` are required.
- For Twilio WhatsApp text-only flows, ElevenLabs and Deepgram are optional.
- Evolution and Twilio WhatsApp are alternative providers. You do not need both for an initial launch.
