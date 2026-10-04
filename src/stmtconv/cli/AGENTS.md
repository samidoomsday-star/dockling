# src/stmtconv/cli — Typer commands

- Follow SPEC 13 and TECH_ARCHITECTURE Section 4.
- One module per command group; each command: load settings → check order state → call one service → render Rich report → exit code.
- Operator messages live in `messages.py`; errors print `StmtconvError.message` + `hint`, never tracebacks with client data.
- No business logic, no direct engine or file-format code here.
