# SaaS Phase 5 — accounts, usage and manual pilot billing

Status: in progress on `saas-phase-5`; owner authorized Phase 5 then Phase 6 on 11 October 2026 (Asia/Dhaka).

## Implementation sequence

1. Restore verified Phase 4 services and preserve records/keys/volumes.
2. Add forward-only account/commercial metadata: immutable plan and payment evidence, scoped entitlement and page reservations, private support/privacy requests and notification acknowledgements.
3. Extend verified-account onboarding, workspace creation, pending invitation management and enforced seat/page limits. Keep invitation acceptance bound to the verified invited email, one use, expiry and current membership.
4. Add real usage/account/help/billing screens with owner-only commercial data. Default to a manual-invoice pilot. No fabricated checkout, customer-supplied payment or external email. Live provider integration, prices and commercial publication require business eligibility and owner decisions.
5. Verify tenant/role/CSRF/idempotency/concurrency, refund/cancellation/payment-failure/duplicate-event cases, actual browser invitation-to-conversion and mobile accessibility. Preserve all existing source/AI/financial gates.
6. Record evidence, limitations and handoff; commit/push the Phase 5 milestone before Phase 6.

## Commercial and acceptance boundaries

Local allowances and fictional invoice values are synthetic development configuration, not approved offers. Production has no implicit free test entitlement. Exact decimal currency values only. Named, immutable manual payment evidence is entered only by a fresh-MFA platform administrator, with event/version/idempotency checks; a customer cannot assert payment. Cancel/refund prevents new processing without withholding already-owned files. Page reservations precede processing, remain conservatively reserved after uncertainty, and do not imply provider dollar charges. Email delivery and merchant checkout remain disclosed integration gates until selected and actually tested; in-app notices and manual invoice records are functional first-pilot alternatives.
