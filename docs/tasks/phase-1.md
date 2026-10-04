# Phase 1 — Foundation

Owner approved Phase 1 on 5 October 2026 (client timezone), accepting the Phase 0 hybrid recommendation. Preserve original phases and existing scoped instructions.

## Scope
- Pinned Python 3.12 package with development extras, portable check script and all module folders.
- Typed YAML/.env settings, validated pricing/category/export stubs, workspace preparation and errors.
- Thin Typer CLI: help/doctor/models download implemented; other inventory commands explicitly unimplemented and nonzero.
- Offline initialization before Docling import; explicit setup-only model network exception with hash verification.
- Rotating JSON logs and console with redaction tests, including sensitive structured fields and exceptions.
- Meaningful configuration/CLI/health/model/log tests; build and installed-wheel validation.
- Beginner-friendly Linux/cloud and Windows/device instructions; Windows execution remains unverified unless an actual runner is available.

## Acceptance
Full check.py gate passes in this cloud environment, package builds/installs, CLI health and repeated model setup execute. Never report placeholders as completed features. Record the Windows PowerShell check as pending until run on Windows. No conversion/order implementation, AI picker or paid API call in this phase.

## Result
Cloud milestone completed: 32 tests passed with none skipped; full lint/format/strict typing, build, model-download hashes, repeatable Linux installer and installed-wheel doctor passed. Windows acceptance remains pending. See PROGRESS.md for evidence and ENVIRONMENT.md for beginner setup steps. Review this milestone before starting Phase 2.
