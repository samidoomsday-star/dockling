# Testing & quality rules

## Definition of Done (every task)
- [ ] `python scripts/check.py` passes (ruff check, ruff format --check, mypy, pytest)
- [ ] mypy strict passes for `src/stmtconv/core`; no `Any`/`type: ignore` without a comment explaining why
- [ ] New logic has tests; bugs get a failing test first
- [ ] From Phase 4: `python -m stmtconv selftest` passes
- [ ] PROGRESS.md updated with how to verify manually

## What must have tests
- Amount parsing: parentheses, trailing/leading minus, DR/CR, thousands and decimal separators, currency symbols
- Date parsing: every generic format, ambiguity flag, year inference incl. Dec→Jan, weekday stripping, out-of-period flag
- Row assembly: multi-line descriptions, inherited dates, noise removal, cross-page continuation
- Running balance (asset and liability), statement checks, every verdict, duplicates warning
- Router fallback decisions and best-result selection
- Order state machine (legal and illegal transitions), atomic writes
- Every export format (golden files), QB no-zero/one-date-format rules, row splitting, OFX determinism and unique FITIDs
- Review round trip (fix, delete, insert_after, invalid cells), spot-check gating
- Deletion leaves no client files; ledger/manifest contain no descriptions
- AI gate (each missing condition), masking, zero network calls when gate closed
- Log redaction

## Tools
- pytest (+ hypothesis for parsers); synthetic PDFs from `tools/synth` generated into `tmp_path`, never committed real data.
- Golden fixtures in `tests/golden/` contain synthetic data only.
- Docling tests marked `@pytest.mark.slow`; `python scripts/check.py --quick` (ruff + mypy + non-slow tests) skips them; the full check runs them.
