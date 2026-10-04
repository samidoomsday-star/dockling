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
- **Status:** superseded by ADR-014 (owner-approved BYOK requirement)
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

### ADR-013: Codex cloud development and original phase tracking
- **Status:** accepted by owner, 4 October 2026.
- **Decision:** import starter into existing Dockling checkout; develop and explore with synthetic data in Codex; preserve original phases 0–10; push reviewable GitHub versions; clone/install on another device for Windows and hardware acceptance. No extra worktree.
- **Consequences:** preserve Kilo files as reference; active workflow in AGENTS. Phase 0 may add migration/setup/reproducible research files but no application implementation. Cloud results cannot establish laptop speed. Explain owner actions in beginner-friendly steps. Review exploration before Phase 1.

### ADR-014: Optional OpenAI-compatible BYOK and capability-aware model picker
- **Status:** accepted by owner, 4 October 2026; supersedes ADR-005's Gemini-only provider and paid-tier assumption.
- **Decision:** guided CLI settings for custom endpoints, hidden key input, connection checks, model discovery/manual IDs, saved selections and supported reasoning effort up to Max. Use a permissively licensed OpenAI-compatible client/adapter; verify exact APIs when implementing Phase 9.
- **Consequences:** AI remains off by default, consent-gated, masked/minimized and validated. Highest effort is provider/model dependent; never silently downgrade. Credentials/personal settings stay outside Git. Review provider terms rather than assuming any paid tier is suitable. Mock API tests; no paid calls during exploration. Docling local models need no BYOK key.

### ADR-015: Phase 1 cloud foundation with device acceptance tracked separately
- **Status:** accepted scope after owner instruction “Start Phase 1”; implemented 4 October 2026 UTC.
- **Decision:** retain the SPEC's foundation feature scope. Verify Python 3.12 CPU setup, packaging, CLI/config/log/privacy behavior and real offline Docling integration here. Provide Windows PowerShell instructions; record the Windows acceptance as pending until actually run, following the owner's request to test dependencies/device behavior later.
- **Consequences:** Phase 1 has explicit nonzero placeholders for future commands. The Linux dependency lock is hash-verified and Windows needs its own validated resolution. Package default configs/model manifest so installation works outside the checkout. AI fields reserve the Phase 9 BYOK plan without enabling API calls. Cloud completion does not establish Windows or financial-conversion readiness.

### ADR-016: Confirm account identity before merging or OFX
- **Status:** implemented under the approved project plan.
- **Decision:** masks are display values, not unique account identifiers. Hash a captured full account identifier locally; otherwise require an operator account group and --confirm-account. Merge also requires matching currency/direction/display account. OFX FITIDs use the private identity and occurrence index. No identity hash or raw account identifier enters anonymous metrics.

## ADR-024 — Final handoff and honest acceptance scope

The owner authorized phases 2–10 without further phase approval. Final cloud code lives on development-phases-2-10; main is not merged. Windows launcher instructions and first-delivery guide accompany a Linux installed-wheel functional check and a reproducible 15-case synthetic supplement. The original owner/public field checklist, Windows/Excel/accounting imports, actual BYOK calls and hardware timings remain separate pending checks. Borderless OCR limitations remain explicit. Max is offered only from advertised or model-specific documented capability evidence.

Explicit close --abandon permits unfinished/failed jobs to undergo the same confined deletion/inventory/scrubbing checks, then failed -> closed; abandoned anonymous metrics do not train delivery quote medians. Known blank pages count as covered, with no fabricated transactions. Clear invoice headers are rejected via configurable markers, but scanned/ambiguous invoices still require operator classification; invoices remain outside V1.
