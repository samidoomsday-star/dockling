# Money, dates & validation rules (SPEC 8–9) — "no silent errors"

- Money is `decimal.Decimal` everywhere. Never construct Decimal from float; never use float arithmetic, `round()` on floats, or pandas numeric dtypes for amounts.
- Unparsable amount or date → flag the row (`AMOUNT_UNPARSABLE`, `YEAR_UNKNOWN`…); never default to 0 or today.
- Date order: if `auto` and all days ≤ 12, flag `DATE_ORDER_AMBIGUOUS` and stop at `NEEDS_REVIEW`. Never guess DD/MM vs MM/DD.
- Running balance: asset `prev − debit + credit`, liability `prev + debit − credit`, tolerance from `settings.balance_tolerance` (0.01). Direction comes from the profile/summary, never inferred silently.
- Every transaction gets a `RowCheck`; every statement gets a `Verdict` per SPEC 9.3. Changing verdict rules requires approval.
- Exports refuse `NEEDS_REVIEW` statements unless `--allow-unverified`, which must also be written into Summary sheet and delivery note.
- Manual fixes set `fixed_by="review"` and increment `manual_fixes`; a fixed statement can only be `VERIFIED_WITH_FIXES`, never plain `VERIFIED`.
- Multi-statement merges must run continuity checks (closing n == opening n+1) and period gap/overlap checks.
- A bug where a wrong value is exported without a flag is severity HIGH: write the failing test first, then fix.
