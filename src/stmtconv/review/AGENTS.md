# src/stmtconv/review — Excel review round trip and spot-check

- Follow SPEC 10 and ADR-010.
- Review workbook columns exactly as SPEC 10.1; highlight MISMATCH yellow, blocking flags orange.
- `apply-review` validates every fix cell first and applies nothing if any cell is invalid (report sheet row + column).
- Spot-check sampling is seeded by order id; results stored in the manifest.
