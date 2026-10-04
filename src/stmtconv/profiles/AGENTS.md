# src/stmtconv/profiles — bank layout profiles (code)

- Follow SPEC 7.4 and ADR-008. The YAML files themselves live in the repo-root `profiles/` folder.
- Pydantic schema with clear errors; loader caches parsed profiles; detector matches fingerprints on page-1 text; `generic` is the fallback.
- `scaffold` writes drafts into the order's `work/` folder only (they may contain client text).
