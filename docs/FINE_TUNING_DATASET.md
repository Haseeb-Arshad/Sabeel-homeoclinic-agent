# Fine-Tuning Dataset Notes

## Dataset files

- Training: `data/fine_tuning/sabeel_clinic_train.jsonl`
- Evaluation: `data/fine_tuning/sabeel_clinic_eval.jsonl`

Generated with:

```bash
venv\Scripts\python.exe scripts\generate_finetune_dataset.py
```

## Coverage included

- Clinic FAQs (timings, address, contact, Lahore visits, online consult)
- Appointment request language and pending confirmation policy
- Roman Urdu and English conversation style
- Safety and legal behavior:
  - no guaranteed cure claims
  - emergency redirection
- Off-topic refusal behavior to keep assistant clinic-focused

## Data format

Each line is one JSON object in OpenAI chat fine-tuning format:

```json
{"messages":[{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

## Fine-tuning workflow (OpenAI)

1. Upload files.
2. Create a fine-tuning job using the training file and optional eval file.
3. Wait for completion.
4. Put resulting model ID in `.env` as `OPENAI_MODEL`.
5. Restart API.

## Important

- This dataset is a strong starter set, but production quality improves by adding real anonymized transcripts from voice/WhatsApp/webchat interactions.
- Keep all examples policy-consistent with clinic legal and safety rules.
