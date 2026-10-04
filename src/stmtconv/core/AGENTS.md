# src/stmtconv/core — pure domain logic

- Follow `.kilo/rules/05-accuracy.md` and SPEC 8–9, 9.4, 12.6.
- No file, network, or subprocess I/O; no imports from other `stmtconv` packages except `errors`.
- `models.py` (RawRow, Transaction, RowCheck, StatementSummary, Statement, enums), `money.py`, `dates.py`, `text.py`, `assemble.py`, `validate.py`, `verdict.py`, `merge.py`, `categorize.py`.
- Decimal only; functions are small, typed (mypy strict) and table-tested.
- Thresholds come in as arguments (from Settings), never as module constants.
