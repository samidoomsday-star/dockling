# Architecture Decision Records

Record any choice that affects structure, dependencies, data model, security, or cost.
Format: Context → Decision → Alternatives → Consequences. Never delete an ADR; mark it superseded.

---

### ADR-001: Local CLI tool for a done-for-you service, not a SaaS
- **Status:** accepted
- **Context:** Roadmap business model is an output service run on the owner's laptop, $0 budget. Self-serve SaaS competitors are established (RESEARCH §3).
- **Decision:** Build an operator CLI (`stmtconv`) with an order workflow; clients only receive files.
- **Alternatives:** Web app with uploads; Streamlit UI; plain scripts.
- **Consequences:** No hosting, auth, or upload security to build. Review happens in Excel. A web UI can come later (V2) on top of the same services.

### ADR-002: Roadmap + research as source of truth; research wins on conflicts
- **Status:** accepted
- **Context:** Several roadmap assumptions (Gemini free tier, Docling-for-everything, CSV format) conflict with current facts.
- **Decision:** SPEC follows research where they conflict; changes listed in SPEC Appendix A.
- **Consequences:** Owner reviews Appendix A and B before Phase 1.

### ADR-003: Hybrid extraction — pdfplumber text engine first, Docling for scanned pages and fallback
- **Status:** accepted
- **Context:** Bank statements have borderless, wrapped, page-spanning tables where table models are weakest (RESEARCH §1–2). Docling is slower on CPU; OCR is the most expensive step.
- **Decision:** `text` engine (word geometry + bank profiles) for pages with a text layer; `docling` for scanned pages and when validation shows the text engine failed; router keeps the result with the best validation score.
- **Alternatives:** Docling only; camelot/tabula; PyMuPDF.
- **Consequences:** Two engines to maintain; much faster and more controllable on digital PDFs; validation becomes the arbiter.

### ADR-004: Decimal money and validation-first design ("no silent errors")
- **Status:** accepted
- **Context:** A wrong number in books is the worst failure; the service's differentiator is proof of correctness.
- **Decision:** `Decimal` end to end; every row gets a check; every statement gets a verdict; exports blocked on `NEEDS_REVIEW` unless explicitly overridden and disclosed.
- **Alternatives:** pandas floats with rounding; best-effort output.
- **Consequences:** More code in `core`, heavy unit tests; pandas not needed.

### ADR-005: Cloud AI only on Gemini paid tier, with per-order consent and masking
- **Status:** accepted
- **Context:** Gemini free tier content may be used to improve Google products and reviewed by humans (RESEARCH §5). Clients send bank statements.
- **Decision:** AI engine off by default; requires `--ai`, `ai_consent=granted` with note, API key, and operator confirmation of paid tier; sends masked table text only; page cap.
- **Alternatives:** Free tier; send images; local LLM now.
- **Consequences:** A few dollars of prepaid credit if used. Local LLM stays V2 (too slow on i5-8250U CPU).

### ADR-006: Permissive licenses only; no PyMuPDF
- **Status:** accepted
- **Context:** Commercial service; PyMuPDF is AGPL/commercial-licensed.
- **Decision:** Use pdfplumber/pdfminer.six (MIT), pypdfium2 (Apache/BSD), Docling (MIT), openpyxl (MIT), reportlab (BSD) and similar. New dependencies need license check + ADR.
- **Consequences:** Slightly slower page rendering than PyMuPDF; no license risk.

### ADR-007: Orders as folders with JSON manifests; no database
- **Status:** accepted
- **Context:** One operator, tens of orders per month, deletion is a core requirement.
- **Decision:** `workspace/orders/<id>/order.json` + subfolders; atomic writes; anonymous `ledger.jsonl` for metrics.
- **Alternatives:** SQLite.
- **Consequences:** Deleting an order is deleting a folder; easy to inspect. If multi-operator or web UI arrives (V2), revisit with SQLite.

### ADR-008: Bank layouts, categories, prices and client-facing texts are data
- **Status:** accepted
- **Context:** Bank formats change; prices will rise after reviews (roadmap); texts get refined.
- **Decision:** YAML (`profiles/`, `config/`) and Markdown templates (`templates/`), validated by pydantic at load.
- **Consequences:** New bank = new YAML + a synthetic or anonymized test; no code change.

### ADR-009: Export OFX 1.02 in V1; QuickBooks Desktop `.qbo` Web Connect in V2
- **Status:** accepted
- **Context:** QBO Online and Xero accept OFX; `.qbo` needs an Intuit bank ID (`INTU.BID`) tied to a real institution, which is error-prone to fake.
- **Decision:** V1 ships OFX with deterministic FITIDs; `.qbo` later with per-client bank ID input.
- **Consequences:** QuickBooks Desktop users get CSV in V1.

### ADR-010: Excel round-trip for review instead of a UI
- **Status:** accepted
- **Context:** The operator already lives in Excel; building a UI is costly.
- **Decision:** Review workbook with fix columns; `apply-review` re-imports and re-validates.
- **Consequences:** Input validation of fix columns must be strict with clear row-level errors.

### ADR-011: Synthetic statement generator as the primary test corpus
- **Status:** accepted
- **Context:** Real statements are private; accuracy must be measurable.
- **Decision:** reportlab-generated statements with ground-truth JSON, rasterized "scanned" variants; real anonymized samples only in Phase 10 and never committed.
- **Consequences:** Generator must cover the hard traits (wrapped rows, page breaks, bracket negatives, no running balance, credit cards).

### ADR-012: Windows PowerShell-friendly commands via `scripts/check.py`
- **Status:** accepted
- **Context:** Windows PowerShell 5.1 doesn't support `&&`; the owner is a beginner on Windows.
- **Decision:** One Python script runs lint/format/type/test gates; all documented commands are single `python …` invocations.
- **Consequences:** Kilo rules reference `python scripts/check.py` and `python scripts/check.py --quick`.
