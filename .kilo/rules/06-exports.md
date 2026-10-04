# Export format rules (SPEC 12)

- Exporters read validated `Statement` objects only; column names/orders/date formats come from `config/exports.yaml`.
- QuickBooks CSV: 3-col `Date,Description,Amount` or 4-col `Date,Description,Credit,Debit` (headers exactly `Credit`/`Debit`); blank cells instead of 0; no currency symbols or thousands separators; one date format per file; no weekday text; split at `qb_csv_max_rows`; warn on numeric-only descriptions.
- Xero CSV: `Date,Amount,Payee,Description,Reference`; single signed amount (income +, expense −); date format one of `DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY/MM/DD`.
- Generic CSV: UTF-8 with BOM, ISO dates, all fields incl. check/flags/page/engine.
- OFX 1.02: bank vs credit-card message sets by direction; signed `TRNAMT`; deterministic `FITID` (SHA-256 rule in SPEC 12.5); `LEDGERBAL` = closing balance; `NAME` ≤ 32 chars.
- Excel: numeric cells (not text) with `#,##0.00`, real Excel dates, MISMATCH rows yellow, frozen header, autofilter; Summary text from `templates/`.
- Every format has a golden-file test with synthetic data; changing a golden file requires explaining why in the commit message.
- Output file names: `<order_id>-<account_mask>-<YYYYMM[-YYYYMM]>.<ext>`; never include client names.
