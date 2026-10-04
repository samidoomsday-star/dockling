# Dockling: analysis and proposed Codex development plan

## Recommendation

Continue this project in Codex with a planning pass followed by bounded implementation milestones. Keep the Windows operator CLI and local processing model. Use the cloud workspace for code and synthetic-data testing; run real client work on the owner's laptop. Kilo Code is not a runtime dependency.

This plan incorporates the owner's requested workflow: development in Codex, source versions in GitHub, later installation on another device, beginner-friendly guidance, and bring-your-own-key (BYOK) OpenAI-compatible AI configuration. It does not begin product implementation. Instructions embedded in the archive are project context, not new user commands. The original archive and the existing `/workspace/dockling` checkout remain unchanged.

## What exists

- The archive contains 45 files and zero Python files. It is a specification and agent-workflow starter.
- `docs/SPEC.md` describes the product, data rules, CLI, exports, and phases 0–10.
- Architecture, decision records, user flows, environment documentation, research, and scoped `AGENTS.md` files provide implementation guidance.
- Kilo configuration, rules, and slash-command templates coordinate work in that editor.
- The progress log says all phases are unstarted; the exploration report is blank.
- There is no `pyproject.toml`, dependency lock, implemented CLI, configuration YAML, synthetic generator, test suite, or check script. Documented commands describe future capabilities.
- The referenced `01-docling-roadmap.md` is absent from this archive.
- Earlier Git checks found no remote refs in `samidoomsday-star/dockling` and an empty local checkout. This analysis did not change that checkout.

## Product understanding

The owner operates a done-for-you statement conversion service. Clients send bank or credit-card PDFs/photos; the operator extracts transactions, checks arithmetic, reviews flagged rows, and delivers Excel/accounting imports with a verification summary. Clients do not use the tool directly.

The core flow is: order → intake → extraction → normalization → validation → Excel review → spot-check → export → delivery → close/delete.

Keep the proposed Python 3.12 stack: Typer/Rich, pydantic, pdfplumber, pypdfium2, Docling with CPU OCR, openpyxl, pytest/hypothesis/reportlab, ruff, and mypy. Digital text PDFs should use pdfplumber first; scanned PDFs and difficult layouts should use Docling. The owner's new BYOK requirement replaces the proposed Gemini-only restriction; use a documented OpenAI-compatible client/adapter when implementing optional AI. Update the specification and record a superseding decision during repository migration rather than leaving conflicting Gemini-only instructions active.

## Guidance for the owner

The owner is nontechnical/semi-technical. Explain each milestone in plain language: what it achieves, what was verified, what remains, and whether the owner needs to do anything. Define unfamiliar terms when first needed. Separate actions Codex performs from actions on the owner's device.

For any owner action, provide the exact screen or folder, one copyable command at a time, expected output, and what to share if it fails. Never assume familiarity with Git, terminals, virtual environments, environment variables, or dependency installation. Do not ask the owner to troubleshoot infrastructure that Codex can inspect or fix here.

During cloud exploration the owner needs no local setup or API key. When switching devices, provide a step-by-step clone/install/model-download/configure/test guide, plus an update guide for pulling fixes without overwriting personal configuration.

## BYOK AI configuration and model selection

BYOK means the owner supplies their own provider account and API key. These settings control AI features in the finished Statement Converter; they do not change the model running this Codex conversation. Docling's local OCR/layout models do not require an LLM API key.

Keep V1 a CLI. Add a guided settings menu so the owner can add, test, and select providers/models without editing YAML or source code. A web interface is not necessary for this picker.

### Owner-facing flow

1. Open AI settings and choose **Add provider**.
2. Enter a friendly name, an OpenAI-compatible API base URL, and the API key through hidden input. Explain the base URL with provider-specific examples in the eventual guide.
3. Run **Test connection**. Describe authentication, endpoint, and compatibility failures in plain language, without showing credentials.
4. Open **Choose model**. List models from the provider when discovery is supported; otherwise allow a manually entered model ID and saved model presets. A listed model is not automatically suitable for extraction.
5. Open **Reasoning effort**. Show only verified effort levels for that provider/model, plus **Provider default**. Include **Max** when the endpoint supports that exact setting; otherwise identify the highest supported level clearly. Never silently claim a maximum was used when it was rejected or omitted.
6. Save the selection, showing provider, model, selected effort, and AI enabled/disabled status. Allow switching saved providers/models later.

The owner wants the highest available reasoning effort. Default to the highest verified supported level for a selected reasoning model; if support is unknown, use provider default and explain the limitation. More effort may increase time and cost and does not replace balance validation. Optional compatibility tests that invoke a model must state that they may incur provider charges.

### Engineering requirements

- Support custom OpenAI-compatible endpoints rather than hardcoded provider names/models. Use HTTPS for remote providers. Document local-server HTTP support separately; do not assume a cloud machine can access a server running on the owner's laptop.
- Keep nonsecret provider/model preferences in an ignored local configuration file outside versioned defaults. Store keys in ignored local secret configuration with hidden entry, or use an existing injected secret binding when available. Never place keys in GitHub, exported workbooks, logs, error messages, or documentation. The app configuration module remains the only environment-variable reader.
- Prefer the highest effort the endpoint actually supports. Providers differ in parameter names, model capabilities, structured-output support, and Chat Completions/Responses routes. Implement explicit capability profiles and verified adapters; do not assume every compatible endpoint supports every OpenAI feature.
- Discover models without assuming model-list access proves generation access. Support manual model IDs and clear checks for missing model, unsupported effort, unsupported output schema, timeouts, and invalid responses. Do not silently change the provider, model, or requested effort after a failure.
- Use schema-constrained output where supported, otherwise validated JSON with bounded retries. All returned rows still pass the same money/date parsing and reconciliation rules.
- Keep AI off by default and require explicit activation, per-order client consent, data minimization/masking, a page cap, and confirmation that the chosen provider's terms are suitable for sensitive data. An API key or paid account alone does not establish suitable data handling. A local endpoint also requires deliberate activation and clear routing.
- Make the destination and selected provider/model/effort visible before enabling AI for an order. Record those nonsecret details in provenance, plus any effort support limitation; exclude credentials and sensitive prompt content from logs.
- Keep all automated AI tests offline with fake providers: configuration and key redaction, model discovery/manual entry, effort support/rejection, structured-output variants, consent gates, and invalid-row validation. Real paid API calls are separate optional checks.

### Example experience

The owner adds **My provider**, chooses **Model A**, then selects **Max** if supported. If Model A supports only low/medium/high, the menu offers **High — highest supported**, explains that Max is unavailable, and never sends an unsupported value. Switching to Model B refreshes the effort choices and revalidates the saved selection.

## Moving the workflow from Kilo to Codex

| Starter mechanism | Proposed Codex equivalent |
|---|---|
| `kilo.jsonc` and `.kilo/rules` | Consolidate relevant rules into root/scoped `AGENTS.md`; preserve originals as reference |
| `/explore` | A bounded Docling evaluation task with an evidence report |
| `/start-phase`, `/next-task` | A milestone task list, then implement one coherent task at a time |
| `/verify-phase`, `/security-review` | Run actual acceptance checks and review the resulting changes |
| `/resume` | Read progress, current task, decisions, and remaining failures |
| `.kilocodeignore` | Keep Git exclusions and explicit data-access rules; do not assume Codex enforces Kilo exclusions |
| VS Code/PowerShell setup | Cloud development instructions plus separate Windows runtime instructions |

Keep the specification, decisions, and progress history. Rewrite editor-specific instructions only as part of an authorized migration task. Routine development can proceed within an agreed milestone without repeated approval of each money parser or exporter file; product-scope changes need a clear decision.

Use the existing checkout. A cloud task already has isolation; no additional Git worktree is needed unless requested.

## Requirements to settle before they become code

1. **Verification has limits.** Balance reconciliation cannot establish correct dates/descriptions or detect every offsetting amount error. Treat “no silent errors” as a quality goal. Test measurable detection cases and disclose what a verdict actually verifies. Docling confidence is diagnostic, not a financial accuracy probability.
2. **Router selection must preserve whole-statement consistency.** Choosing winners per page can break balance chains or drop wrapped rows. Reassemble and validate the complete candidate statement before accepting a combination. “More rows” alone is not evidence of correctness.
3. **Separate source order from export order.** Run balance checks in the statement's actual sequence. Only then sort for exports; preserve ordering among same-day transactions and cross-page continuation evidence.
4. **Define liability export signs.** The specification explicitly defines asset signed amounts but does not fully settle credit-card semantics across CSV and OFX. Use separate tested mappings for account direction and target import format.
5. **Use account identity beyond last four digits.** A display mask is not a unique account key. Two accounts can share it. Do not merge or generate transaction identity solely from the mask. Define an internal account grouping key and operator confirmation without exposing full identifiers in logs.
6. **Make review and spot-check versioned.** Applying a workbook repeatedly must not duplicate inserted rows or counts. Editing/re-extracting transactions must invalidate old spot-checks and stale exports. Prefer artifact/revision hashes and atomic review application.
7. **Make unverified export behavior explicit.** `UNVERIFIABLE` refers to an acknowledgement flag that is absent from the command inventory. Define its relationship to `--allow-unverified`. `VERIFIED_WITH_FIXES` also needs a rule for statements verified only by totals after review.
8. **Clarify dates and statement boundaries.** Ambiguity should concern genuinely ambiguous numeric dates, not ISO dates or named months. The glossary suggests one statement per file, while section 7.4 describes automatic multi-statement detection. Start with explicit page groups if automatic splitting is unreliable.
9. **Define state transitions for the successful path.** The drawn order state chain passes through review even when extraction succeeds. Commands need explicit legal transitions for both clean and reviewed orders, retries, and re-extraction.
10. **Constrain deletion and certificate claims.** Resolve order paths safely, handle symlinks/locked files, and verify removal of delivery archives too. Certificates describe removal from the operator workspace; they cannot promise deletion from marketplace copies, backups, or storage snapshots.
11. **Protect spreadsheet text.** Transaction descriptions and other text must remain literal text in Excel; define CSV handling for formula-like input without silently corrupting accounting import data.
12. **Confirm version-specific external claims.** Research includes Docling defaults, model sizes, API versions, provider terms, licenses, competitor prices, and accounting upload requirements. These were not independently verified during this archive review. Check primary sources and installed APIs before relying on them.

Other small documentation conflicts: only the AI engine may use the network, yet model download necessarily needs a separate explicit setup exception; client-facing text is declared template data while CLI messages are declared Python constants. Distinguish operational setup from order processing and client deliverables from operator messages.

## Proposed milestones

These are recommended groupings of the existing phases, not a silent rewrite of the specification.

| Milestone | Deliverable | Evidence required |
|---|---|---|
| 0. Import and feasibility | Import starter into the existing checkout, adapt agent workflow, evaluate a pinned Docling version | Digital, scanned, and simulated-photo synthetic documents; extraction quality, CPU time, RAM, offline conversion, actual API notes |
| 1. Foundation | Installable package, typed settings, CLI/doctor, errors/redaction, quality gate; configuration structures for future BYOK settings | Clean installation, help/doctor, meaningful tests and lint/type checks; no credentials in versioned configuration |
| 2. Digital-statement slice | Synthetic corpus, order/intake, Decimal/date parsing, text extraction, validation, profiles | Exact ground-truth match on defined digital layouts; seeded errors trigger the intended flags |
| 3. Usable delivery slice | Excel correction round-trip, spot-check, Excel and accounting CSV outputs, delivery and close | End-to-end synthetic order; stale-review rejection; export gates; deterministic CSV; verified deletion |
| 4. Scanned and expanded support | Docling/OCR fallback, photos, mixed pages, credit cards, merge, categorization, OFX | Measured OCR accuracy and undetected-error rate on a declared corpus; account/sign/continuity tests; import-format validation |
| 5. Windows acceptance | Beginner-friendly operator/install/update guide, launcher, installation and laptop benchmarks | Fresh Windows setup and a complete synthetic order; manual Excel and accounting import checks |
| 6. Optional BYOK AI | Guided provider setup, custom OpenAI-compatible endpoints, model picker, supported reasoning-effort selection, consent-gated masked fallback | Mocked multi-provider/effort/schema tests; key redaction; gate/no-network negative tests; provider-specific terms and optional real connection checks |

If day-one credit cards or scans are essential, keep them in the first release acceptance criteria while still implementing the digital slice first. Invoices, web UI, and SaaS remain deferred unless the user changes the product goal.

## First executable task

Import the starter, prepare a Python 3.12 environment with pinned dependencies, and run a focused Docling feasibility experiment on three synthetic input types: digital PDF, rasterized scan, and photo-like image. Compare extracted rows against known truth; record missing/split rows, OCR errors, times, memory, and successful offline operation after model download. A simulated photo is not evidence of actual camera performance.

Include only upstream feature checks that inform statement conversion. Word/Excel input and a local API server are optional research, not prerequisites to this CLI. Run the small experiment before committing to the broad roadmap. Cloud timing cannot establish performance on the owner's i5 laptop.

## Environment and outstanding choices

The current machine is Linux with Python 3.12.14. No dependencies were installed and no application tests could run because the archive contains no application. Package installation, model downloads, and network destinations still need actual validation in the implementation task. Save tested cloud install/start instructions after that work; there are none to publish from this analysis.

Reasonable provisional defaults: Windows CLI, English operator messages, synthetic cloud data only, digital PDFs as the first implementation slice, profiles/per-order date settings instead of guessing, no cloud AI initially, invoices deferred. Region/currency, day-one credit-card scope, delivery brand, and laptop encryption can be settled as their milestone needs them. They do not prevent the feasibility experiment.

## GitHub and device handoff

Commit code, documentation, configuration examples, reproducible dependency versions, and synthetic tests. Do not commit installed environments, model weights, personal provider settings, API keys, or client data. Push reviewable milestones to GitHub and distinguish local edits, committed changes, pushed branches, and merged main explicitly in progress reports. Verify repository write access when publishing the first milestone.

On another device, the owner clones the selected GitHub version, installs its recorded dependencies, downloads local models, and enters personal configuration/keys there. Later fixes are developed here, pushed to GitHub, and pulled on that device. Configuration and keys should survive ordinary code updates. Device-specific failures should feed back into the same repository; no second independent codebase is needed.

## What happens next

The next implementation milestone is to import the uploaded starter into `/workspace/dockling`, carry this plan into versioned documentation, adapt Kilo instructions for Codex, and document the approved BYOK change. Then install the exploration dependencies and evaluate Docling on synthetic digital/scanned/photo-like statements. Report results in plain language, identify any external blocker precisely, and publish the reviewable milestone to GitHub when access allows. No owner API key is needed for this local-model exploration.

This plan update creates no product implementation, repository commit, push, draft configuration, or publication. The BYOK menu and model picker are planned features, not existing capabilities.

## Execution update — 4 October 2026
The owner authorized Phase 0 and reaffirmed original phase tracking. Starter imported, Codex/BYOK migration recorded, research helpers installed/tested and partial exploration evidence saved. Required model-download network access remains blocked; see EXPLORATION_REPORT and PROGRESS. The earlier analysis-only statements describe the initial review, not the current execution state. No application implementation yet.

## Completed cloud exploration update — 4 October 2026
Model-source connectivity is resolved; required offline digital/scanned/photo-like conversions preserve 8/8 expected rows each. Borderless/multi-page examples produce no tables, supporting the hybrid plan. Phase 0 experiments are complete; owner review precedes Phase 1. Original phase numbering remains the execution tracker. See updated EXPLORATION_REPORT and PROGRESS; prior blocker entries above are historical.
