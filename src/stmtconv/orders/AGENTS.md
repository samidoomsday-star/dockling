# src/stmtconv/orders — manifests, state machine, ledger

- Follow SPEC 6, 15.3 and ADR-007.
- `order.json` model (pydantic), atomic write (`*.tmp` → `os.replace`), `transition()` enforcing SPEC 6.3, `paths.py` for all order folder paths.
- Ledger lines contain only anonymous metrics (no alias, file names, descriptions, amounts).
