# Run the first controlled customer pilot

Dockling now has a browser app: customers sign in, upload statements, review rows against source pages, download six output formats and request removal. Owners manage accounts, limits, optional BYOK connections, manual invoice evidence and scoped support. This guide explains how to turn the tested engineering version into a small, observable pilot.

**Current result: pilot preparation is ready and the tested worker advisory gate passes with zero high/critical findings.** See [the security remediation](PHASE8-SECURITY-REMEDIATION.md). Independent review, licensing, a public host and permitted field/import tests have not been completed; customer launch remains pending. Nothing in this guide authorizes spending, invitations, publication or real document processing. Full Phase 8 needs an actual pilot cycle; see [its task](../tasks/saas-phase-8.md).

## What you need to decide

| Choice | What it controls | Current status |
| --- | --- | --- |
| Business country and permitted customer locations | Merchant eligibility, contracts and data rules | Undecided; likely US/EU buyers do not determine this |
| Hosting region, provider and monthly spending cap | Where documents live and resources may be purchased | Undecided; free hosting requires capacity/eligibility verification |
| Domain and identity administrator | Public address, secure sign-in and recovery | No public deployment |
| Pilot size and page/job/team limits | Capacity and customer entitlement | Measure selected hosting first; local test allowances are not an offer |
| Price, cancellation/refund rules and payment method | Truthful commercial terms | Manual invoice pilot is the starting direction; no approved price |
| Retention, backup expiry and recovery targets | What deletion and reliability promises can be made | Verify the actual host; local restore results do not establish these |
| Support contact, hours and responsible operator | Customer help and incident response | Must be real and monitored before invitations |

You can keep developing and testing fictional documents while these choices remain undecided. Before selecting a free provider, read [capacity and hosting](CAPACITY-AND-HOSTING.md). A free React preview does not provide the Python OCR worker, identity, private storage, database or backups.

## Instructions for your next coding assistant

Paste this after opening your clone of `saas-phase-7`:

> Read AGENTS.md, docs/DEVICE_SETUP.md, docs/PROGRESS.md, docs/tasks/saas-phase-7.md, docs/tasks/saas-phase-8.md, docs/saas/PHASE7-STAGING.md, docs/saas/PHASE8-PILOT.md and deploy/staging/README.md. Inspect the actual branch and existing configuration first. Set up and verify the real app with fictional documents, preserving matched database/vault/backup keys, volumes and prior evidence. Keep real inference paused and custom OpenAI-compatible BYOK/model/actually supported Max available. Resolve reported native critical/high findings without suppression and recheck the strict scanner. Report pending licensing/security reviews. Prepare a concrete selected-host deployment and measured budget using my approved provider/region/limits; do not buy resources or publish until authorized. Never call a loopback test a public deployment or a successful CSV download a verified accounting import. Complete independent work, then explain any missing owner choices plainly. Leave secrets and customer documents out of Git and chat. Do not merge main without authorization.

## Keep a private launch ledger

Use a restricted private folder outside Git. Record each item as **pending**, **failed** or **passed with observed evidence**; an empty field means pending. Include the tested source SHA, image digest, actual environment, date, responsible person and private evidence reference. References must not contain account numbers, statements, passwords, API keys or signed download URLs.

The ledger needs: strict worker scan; independent review; dependency/model terms; selected-host verified TLS/authentication and tenant/role denial; actual capacity and cost; monitored alerts; matched encrypted restore and newer deletion reconciliation; permitted field/source review; each promised destination import/version/date/sign/duplicate check; customer walkthrough and accessibility; approved offer/contact/retention; owner publication decision. Preserve the separate field observations described in [Phase 7](PHASE7-STAGING.md). A validator can check record consistency, but cannot verify legal permission or prove an operator's statement.

## Before inviting anyone

1. Resolve the critical/high findings and record a strict passing scan for the **deployed** image. Close or block independent-review findings. Verify actual dependency/model redistribution and service terms.
2. Provision the approved host and domain using the reviewed [staging templates](../../deploy/staging/README.md); configure separate service credentials and secure identity. The templates still require actual deployment. Test private networking, backups, alerts, restart, restore and deletion on that host. Never aim the disposable local restore helper at production.
3. Use fictional data to rerun the genuine sign-in/upload/review/export/removal journey. Measure realistic page counts and concurrency. Keep AI paused until the actual provider route, permission, terms, caps, cleanup and supported effort are verified; test providers with fakes until paid calls are explicitly authorized.
4. Obtain permission for field samples and keep proof privately. Review all expected rows and source dates/descriptions, then actually import promised formats into the intended software versions. A passing balance calculation does not prove descriptions or dates.
5. Measure infrastructure, storage/egress, provider charges, human review and support; approve a price and narrow supported offer. Ensure a real contact route and published policies match actual behavior. Review first-time-user and manual accessibility findings.
6. Present the concrete deployment, evidence, limits and offer to the owner. After explicit publication/invitation approval, open only the approved cohort and limits. Do not publish a simulated purchase or imply automated checkout exists.

## Run each pilot account

| Step | Actual owner/customer action | Evidence to retain privately |
| --- | --- | --- |
| Invite and sign in | Owner uses verified onboarding and the existing exact-email invitation; administrator uses fresh MFA | Correct workspace/role/seats; recovery/contact route |
| Agree scope and billing | Confirm supported documents, page limits, retention, price and terms | Approved offer and actual external payment confirmation |
| Activate access | Administrator records an immutable plan/invoice and independently verified payment evidence | Unique reference and entitlement snapshot; no fabricated paid status |
| Convert and review | Customer uploads permitted material, handles protected-PDF password privately, reviews every relevant source mismatch | Layout/page/row counts, queue/review timing and unresolved limitations |
| Deliver and import | Generate approved formats, verify delivery hashes, import into promised destinations | Destination version, row/date/sign/duplicate results; failed imports remain failed |
| Help | Customer opens a private support request; document assistance needs a separate scoped, expiring grant | Outcome and support time; no implicit administrator document access |
| Close or renew | Apply the agreed cancellation, retention and backup-expiry policy; verify live removal and actual external refunds where due | Removal/retry receipts, remaining backup expiry and payment evidence |

Manual invoice forms record external evidence; they do not charge a card or send a refund. Email delivery and hosted checkout are not implemented payment/contact promises. Do not announce either as working until its own integration and real tests are complete. BYOK costs are additional to hosting; never silently switch a customer's provider/model or downgrade an effort setting.

## When to stop and how to recover

Pause new intake and invitations immediately for suspected cross-account exposure, missing/partial removal, uncertain provider charge/cleanup, unverified recovery, exhausted capacity or material financial/import errors. Fence affected artifacts and provider sends, revoke affected authority, preserve minimal private evidence, and follow the approved notification policy. No automatic external email or refund is triggered by this guide.

Use [operations procedures](PHASE6-OPERATIONS.md). An image rollback alone is insufficient when schema, object versions, identity, entitlements or deletion history changed: quiesce writers, use the matched verified recovery set, reconcile newer deletion/revocation/payment records, then repeat private service and tenant checks. Restore only to an authorized target. Never delete active volumes or regenerate matched keys to make a test green.

## Finish the cycle before expanding

Observe an actual statement, billing and retention cycle. Keep a private findings list with impact, reproducible sanitized example, affected version, source cause, owner and verification result. Fix high-impact conversion, privacy, import and usability issues before adding accounts; rerun the affected tests and deployed-host journey after each release.

Review measured raw extraction versus reviewed results, import failures, queue/capacity, total cost, support time, refunds, removal and restore outcomes. Make customer claims from those observations. The owner then decides whether to extend the cohort, revise the offer or stop. Broader publication and merging `main` remain separate explicit decisions.
