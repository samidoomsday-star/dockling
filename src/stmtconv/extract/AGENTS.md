# src/stmtconv/extract — engines and router

- Follow `.kilo/rules/04-extraction.md`, `07-ai-cloud.md`, TECH_ARCHITECTURE Sections 5.1 and 7.
- `base.py` defines the `Extractor` protocol and `ExtractionResult`; engines return strings in `RawRow`, parsing happens in `core`.
- `router.py` is the only caller of engines; it records engine + reason per page in the order manifest.
- `docling_engine.py` imports Docling lazily and builds one converter per run; honour offline mode and thread count.
- `ai_engine.py` is the only module allowed to use the network, and only after `privacy.ai_gate.check()` passes.
- No bank-specific logic: everything layout-specific comes from the profile object.

Owner-approved amendment: ADR-014 replaces Gemini-only AI with OpenAI-compatible BYOK and supported model/effort selection. Routine work inside an approved task does not need repeated approval; preserve consent, masking and validation. Active Codex rules are in root AGENTS.md.
