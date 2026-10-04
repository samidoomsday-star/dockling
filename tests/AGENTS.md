# tests — unit, golden, e2e

- Follow `.kilo/rules/08-testing-quality.md`.
- `unit/` mirrors `src/stmtconv`; `golden/` holds expected CSV/OFX/JSON built from synthetic data only; `e2e/` runs full order flows on generated statements in `tmp_path`.
- Mark Docling-dependent tests `@pytest.mark.slow`; block sockets in AI and privacy tests.
- Never add real statements or client-derived text to the repo.
