# Environment & Local Setup — Statement Converter

> Derived from `docs/SPEC.md` Sections 4 and 16. If this conflicts with SPEC, SPEC wins. When adding or renaming a variable or setting: update `stmtconv/config.py`, `.env.example`, `config/settings.yaml`, and this file in the same commit.

## 1. Required tooling
| Tool | Version | Notes |
|---|---|---|
| Windows | 10 or 11 | Owner laptop: i5-8250U, 12 GB RAM, no usable GPU |
| Python | 3.12.x (64-bit) | "Add to PATH" during install; `py -3.12 --version` |
| Git | recent | Git for Windows |
| VS Code + Kilo Code | recent | Terminal: Windows PowerShell 5.1 is fine (no `&&` needed) |
| Microsoft Excel or LibreOffice Calc | any | For review workbooks |
| Disk | ≥ 5 GB free | ~1 GB Docling models + venv + workspace |

No Tesseract, CUDA or Docker required (RapidOCR via Docling's default install).

## 2. Environments
| Name | Purpose | Where |
|---|---|---|
| `local` | Real client work | Owner laptop, `workspace/` on an encrypted disk, outside OneDrive |
| `test` | Automated tests | pytest temp folders, synthetic data only, network blocked in AI tests |

## 3. Local setup (after Phase 1 exists)
1. `git clone <repo> C:\work\statement-converter` then `cd C:\work\statement-converter`
2. `py -3.12 -m venv .venv`
3. `.venv\Scripts\Activate.ps1` (if blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)
4. `python -m pip install --upgrade pip`
5. `pip install -e ".[dev]"`
6. `copy .env.example .env` and edit values (Section 4)
7. `python -m stmtconv models download` (≈1 GB, use Wi-Fi, one time)
8. `python -m stmtconv doctor`
9. `python scripts/check.py`
10. `python -m stmtconv selftest` (from Phase 4)

## 4. Environment variables
| Variable | Required | Used by | Example / format | How to get it |
|---|---|---|---|---|
| `STMTCONV_WORKSPACE` | yes | all | `C:\work\statement-converter\workspace` | Choose a folder on the encrypted system drive, **not** under OneDrive/Dropbox |
| `STMTCONV_LOG_LEVEL` | no | logging | `INFO` | `DEBUG` only while developing with synthetic data |
| `STMTCONV_NUM_THREADS` | no | docling | `4` | Physical cores of the CPU (i5-8250U has 4) |
| `STMTCONV_OFFLINE` | no | config | `true` | Keep `true`; set `false` only for `models download` (the command handles this itself) |
| `DOCLING_ARTIFACTS_PATH` | no | docling | `C:\work\statement-converter\models` | Created by `models download` |
| `GEMINI_API_KEY` | only for Phase 9 / `--ai` | ai engine | `AIza…` | https://aistudio.google.com/apikey → create key in a project **with billing/prepay enabled** (paid tier) |
| `STMTCONV_AI_PAID_TIER_CONFIRMED` | only with `--ai` | ai gate | `false` | Set `true` only after checking AI Studio shows the project's plan as "Paid"; free-tier data may be used by Google |
| `STMTCONV_AI_MODEL` | only with `--ai` | ai engine | a current Gemini Flash model id | AI Studio model list; confirm it is available on your tier |

## 5. Config files (committed, no secrets)
| File | Holds |
|---|---|
| `config/settings.yaml` | `balance_tolerance: 0.01`, `fallback_mismatch_ratio: 0.05`, `min_rows: 1`, `spot_check_rows: 10`, `qb_csv_max_rows: 1000`, `retention_days_after_delivery: 7`, `ai_max_pages_per_order: 20`, `max_file_mb: 100`, `max_pages_per_order: 500`, `date_out_of_period_days: 7`, default currency, default output date format, default sec/page by kind |
| `config/pricing.yaml` | Packages (Basic/Standard/Premium/Monthly), page limits, price ranges, add-on percentages |
| `config/categories.yaml` | Ordered keyword/regex rules → category |
| `config/exports.yaml` | Column names and orders per export format, date formats allowed per format |
| `profiles/*.yaml` | Bank layouts (no client data) |
| `templates/*.md` | Delivery note, data-handling statement, verification summary, deletion certificate |

## 6. Rules
- Never commit `.env`, anything under `workspace/`, `models/`, `samples/private/`, or any real statement.
- Only `stmtconv/config.py` reads environment variables; it validates at startup and fails fast with a clear message.
- Keep the laptop disk encrypted (BitLocker or Windows Device Encryption) and the workspace out of cloud-sync folders.
- Test with synthetic statements; real anonymized samples live only in `samples/private/` (ignored) and are used in Phase 10 acceptance.
- Rotate `GEMINI_API_KEY` if it was ever pasted into a chat, log, or commit.
