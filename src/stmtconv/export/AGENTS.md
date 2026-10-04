# src/stmtconv/export — output writers and delivery

- Follow `.kilo/rules/06-exports.md` and SPEC 12, 14.1.
- One module per format; each takes validated `Statement`s + export spec from `config/exports.yaml` and returns written paths.
- Refuse `NEEDS_REVIEW` unless the caller passes `allow_unverified=True`; then write the disclosure text.
- Templates in `templates/*.md` are rendered with order data only (no free text from documents).
- Every writer has a golden-file test in `tests/golden/`.
