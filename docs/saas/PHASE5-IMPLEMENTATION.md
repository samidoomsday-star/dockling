# SaaS Phase 5: accounts, usage and manual pilot billing

Implemented on `saas-phase-5` for synthetic local acceptance. This builds on Phases 1–4 and preserves the Python CLI. Public deployment and the independent release gates remain pending.

## Customer experience

A genuinely signed-in user with a verified email can create a workspace. Owners can invite editors/viewers, see pending invitation expiry and revoke links; acceptance still requires the exact verified email, an unused unexpired link and available seats. Account and usage shows active/pending seats and the current UTC calendar month's used, reserved and remaining pages. Help offers private support, plan and owner-only privacy requests. Workspace updates have human-readable categories and per-user read receipts. Editors/viewers cannot read owner billing records, and platform administrators do not acquire implicit document membership.

Private pages use the existing calm mint, peach and lavender palette, mobile layouts and accessible labels. Creating an invitation preserves its copyable link while refreshing metadata; switching identity/workspace clears private caches.

## Processing limits

An inspection reserves the configured maximum job pages before processing (40 by default). Extraction settles this reservation to the actual physical source page count. Reprocessing the same immutable sources in the same calendar month does not double count. A different source set or a new month needs a new reservation. Uncertain/failed processing stays reserved for review; removal does not erase usage. The workspace transaction lock serializes simultaneous page and seat requests. Pending unexpired invitations hold seats.

Local development allows 500 pages/month and 10 seats without a paid invoice. These are test settings, not commercial offers. Production has no implicit development allowance: processing waits for an explicit active entitlement. Expired, cancelled and refunded entitlements never fall back to the development allowance. Existing authorized records/downloads remain available; cancellation/refund fences queued/running intake, extraction and AI publication, without resetting reservations.

## Manual invoices and owner operations

An administrator with fresh MFA can create an immutable private plan and invoice, then record independently verified manual evidence with a unique reference and expected version. Exact two-decimal strings carry amounts throughout Python, JSON and React; floats are rejected. Legal issued/failed/paid/refunded/cancelled transitions and command replay are enforced. A paid invoice snapshots its plan limits into an entitlement; terminal states cannot be resurrected. Cross-workspace evidence references cannot be reused. The SQL service role cannot update immutable plans or evidence.

This form records evidence; it does not debit a card, make a bank transfer or issue a real refund. Downloaded JSON is an invoice record, not a compliant tax invoice. The operator must independently verify the actual external payment/refund. Prices and merchant eligibility are undecided; plan publication is disabled, checkout/portal explicitly reject use, and no real offer is advertised. Manual invoicing is the approved first-pilot direction. Hosted payment-provider signing/webhooks, taxes, checkout and email delivery remain separate integrations requiring eligibility and actual tests.

Private support responses require fresh administrator MFA and a current request version. Customer messages are bounded, rate-limited and should contain no statements, account identifiers or keys. Support/privacy requests grant no document access and do not automatically export or erase data. The existing explicit scoped support grants remain necessary for document assistance.

## Verification

Final local backend suite: **109 passed** on real PostgreSQL/private storage, including nine account/commercial cases covering concurrent quotas/invitations, verified onboarding, exact amounts, immutable plans, cross-tenant/role/CSRF/MFA checks, evidence duplicates/failure/replay/expiry/refund/cancellation and actual rejected worker publication after revocation. The original converter gate passes **315 tests**; frontend unit/demo gates pass **42 / 19**. Strict typing, formatting, API build, model hashes and actual worker SQL/network/container restrictions passed. OpenAPI 0.5.0 retains all 33 feature mappings and distinguishes implemented manual routes from planned provider integrations.

Final real-browser and GitHub evidence is recorded in `docs/tasks/saas-phase-5.md` after execution. No real statements, paid inference, payments, external email, public deployment or main merge occurred.

## Try it on another device

Follow `docs/saas/LOCAL-SETUP.md` and `docs/DEVICE_SETUP.md`; use the newest completed SaaS branch. Preserve `.local-saas` credentials, the vault key and persistent volumes. Run setup/migrations and rebuild the worker/API frontend on the receiving device. Use fictional statements and accounts. A clone transfers code and instructions, not installed software or private jobs/keys.
