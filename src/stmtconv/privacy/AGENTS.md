# src/stmtconv/privacy — redaction, masking, AI gate, deletion

- Follow `.kilo/rules/03-security.md` and SPEC 11.2–11.3, 14.2, 15.2.
- `redact.py` logging filter; `mask.py` account/email/phone masking; `ai_gate.py` four-condition check; `deletion.py` close-order deletion + verification + certificate.
- Changes here need approval (security-sensitive). Every function has tests, including negative cases.
- Deletion must never report success unless a re-scan finds no client files.

Owner-approved amendment: ADR-014 replaces Gemini-only AI with OpenAI-compatible BYOK and supported model/effort selection. Routine work inside an approved task does not need repeated approval; preserve consent, masking and validation. Active Codex rules are in root AGENTS.md.
