# Cloud AI rules (SPEC 11) — off by default

- The AI engine runs only if `privacy/ai_gate.py` passes all four checks: `--ai` flag, `order.ai_consent == "granted"` with note, `GEMINI_API_KEY` set, `STMTCONV_AI_PAID_TIER_CONFIRMED=true`. Otherwise skip with a logged reason; no network call.
- Never suggest or implement using the Gemini free tier for client data (free-tier content may be used by Google).
- Send only masked transaction-table markdown of failing pages: no images, file names, headers, or account holder names. Masking via `privacy/mask.py` (digit runs ≥ 8 → last 4, emails, phones).
- Enforce `ai_max_pages_per_order`; temperature 0; JSON response schema = RawRow cells; timeout and 2 retries.
- AI rows go through the same normalization and validation; mark `engine="ai"`; never trust AI output to "fix" balances.
- Log only page number, status, latency, token counts.
- Tests use a fake client; sockets are blocked in AI tests; never call the real API in automated tests.
- AI is not used for categorization or any other feature in V1.
