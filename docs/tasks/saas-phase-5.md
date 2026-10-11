# SaaS Phase 5 — accounts, usage and manual pilot billing

Status: implemented locally and pushed on `saas-phase-5`; owner authorized Phase 5 then Phase 6 on 11 October 2026 (Asia/Dhaka).

## Implementation sequence

1. Restore verified Phase 4 services and preserve records/keys/volumes.
2. Add forward-only account/commercial metadata: immutable plan and payment evidence, scoped entitlement and page reservations, private support/privacy requests and notification acknowledgements.
3. Extend verified-account onboarding, workspace creation, pending invitation management and enforced seat/page limits. Keep invitation acceptance bound to the verified invited email, one use, expiry and current membership.
4. Add real usage/account/help/billing screens with owner-only commercial data. Default to a manual-invoice pilot. No fabricated checkout, customer-supplied payment or external email. Live provider integration, prices and commercial publication require business eligibility and owner decisions.
5. Verify tenant/role/CSRF/idempotency/concurrency, refund/cancellation/payment-failure/duplicate-event cases, actual browser invitation-to-conversion and mobile accessibility. Preserve all existing source/AI/financial gates.
6. Record evidence, limitations and handoff; commit/push the Phase 5 milestone before Phase 6.

## Commercial and acceptance boundaries

Local allowances and fictional invoice values are synthetic development configuration, not approved offers. Production has no implicit free test entitlement. Exact decimal currency values only. Named, immutable manual payment evidence is entered only by a fresh-MFA platform administrator, with event/version/idempotency checks; a customer cannot assert payment. Cancel/refund prevents new processing without withholding already-owned files. Page reservations precede processing, remain conservatively reserved after uncertainty, and do not imply provider dollar charges. Email delivery and merchant checkout remain disclosed integration gates until selected and actually tested; in-app notices and manual invoice records are functional first-pilot alternatives.

## Observed acceptance

- 109 real PostgreSQL/private-storage/API tests; 315 original converter tests; strict lint/format/types; OpenAPI 0.5.0 (147 operations, 157 schemas, seven examples, 33 feature mappings).
- Final frontend check: 42 unit tests and 19 demo browser journeys, plus TypeScript/API build.
- Complete genuine OIDC/OTP restricted-worker/fake-AI journey passes new-account creation, verified-email invitation, upload/conversion/source checks/actual CSV download, exact usage, private support/reply/notices, manual invoice issued/paid/refunded, owner entitlement fencing, all six older input/export cases, live removal, grant revocation and mobile axe/layout. Fictional provider only.
- Fixed a real invitation-link unmount issue; test selectors now use actual writer CSV naming, visible response prefix and the specific named support grant. No source, financial, isolation, download or revocation assertions were relaxed.
- Source `ae3b1257` is pushed. GitHub frontend run [38120264673](https://github.com/samidoomsday-star/dockling/actions/runs/38120264673) passed; full SaaS run [38120264665](https://github.com/samidoomsday-star/dockling/actions/runs/38120264665) is checked to completion. Later evidence follows when observed. Main remains unmerged.
- The Phase 6 dependency audit identified outdated packaging-tool advisories; fixing the pinned pip/setuptools and rerunning conversion is part of the next milestone. This is not a production-release signoff.
