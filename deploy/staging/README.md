# Selected-host synthetic staging handoff

These are reviewable Linux host templates, not an installed/public deployment. Use fictional data only while the critical/high native scan is blocked. The loopback rehearsal is documented in `docs/saas/PHASE7-STAGING.md`.

## Provision before starting

1. Choose the actual host, region, domain and maximum monthly cost. Confirm Linux x86 compatibility, pinned wheels/model hashes, durable disk, adequate CPU/RAM and a private worker-to-DB route. The API and worker need an approved shared Unix broker directory; one API process owns it. Independently restartable containers are supported; multiple API processes or Cloud Run instances need another broker architecture.
2. Provision a dedicated `dockling_staging` PostgreSQL database with the existing migration-owner, restricted `dockling_app` and `dockling_worker` roles/grants, separate verified TLS credentials/routes, and the forward schema migrations. Adapt the local initialization/migration examples to the selected host privately. Do not expose database administration or repurpose a customer/production database.
3. Provision a dedicated private `dockling-staging-*` bucket, restricted service credentials, retention/backups and HTTPS endpoint. Provision Keycloak or a compatible selected identity service with HTTPS discovery/keys, the `dockling-staging-web` confidential client, exact HTTPS callback, authorization-code/PKCE and tested owner MFA. Create named synthetic memberships and test entitlements through reviewed privileged setup; the fictional local seed is not a customer onboarding or billing procedure.
4. Install the hash-locked Python/Node/model dependencies and build `frontend` in API mode. Build the worker from the same reviewed source. Give it only its restricted DB credential, verified private CA, read-only verified models and private broker; keep public TCP/DNS, Docker socket and storage/admin credentials inaccessible. Re-run container and database isolation on the selected network.
5. Copy `config/staging-server.env.example` into `.staging-saas/server.env`, replace placeholders privately, and set file mode 0600. Generate independent random session/client/storage secrets and a neighboring private `ai-key.env` vault key; preserve these as matched recovery material. Fill actual administrator issuer/subject entries. Keep `AI_DISPATCH_ENABLED=false` and `COMMERCIAL_OFFERS_ENABLED=false`. Never reuse the loopback test CA for public TLS.
6. Review paths/users/proxy limits, then adapt `dockling-api.service.example` and `Caddyfile.example`. They use one API listening only on 127.0.0.1:8000 behind valid public HTTPS. Disable access/body/header logs. Open only intended public HTTPS/identity routes, with private database/storage/admin access. The scripts do not install system services, open a firewall or buy a domain.

The candidate API command, run as an unprivileged dedicated service user after provisioning:

```bash
/srv/dockling/.venv/bin/python /srv/dockling/scripts/saas-server.py --config /srv/dockling/.staging-saas/server.env --broker /run/dockling-broker/socket --synthetic-staging
```

It refuses inference/commercial-offer activation, a non-staging DB/bucket, missing private vault/admin material, unverified DB/schema or unhealthy storage. It does not create schemas, grant memberships or seed payments. Protect the broker parent and mount it to the separately isolated worker with the correct UID/access. Review systemd sandbox options against the actual layout before installation.

After starting all services, run the read-only preflight from the target host:

```bash
.venv/bin/python scripts/saas-staging.py check --config .staging-saas/server.env
```

A pass checks connectivity/denials/security headers; it does not approve launch. Reproduce the synthetic workflow on actual HTTPS with newly provisioned fictional identities; the repository's `saas-rehearsal-*` acceptance scripts intentionally target only their fixed loopback namespace and cannot be redirected to an arbitrary public account.

## Prove before customer use

Run selected-host upload/parser abuse, tenant/MFA restrictions, all six outputs and real import acceptance, source checks, rate/seat/page limits, stale updates, interruption/reclaim, AI teardown and deletion retry. Prove matched encrypted restore and migration rollback using that host's disposable resources. `saas-ops.py` is restricted to the original local loopback stack; it is not a staging/production backup tool. Record actual alert/support ownership, retention/expiry, restore times, queue/load, monthly allocations and provider/legal terms. Keep receipts/document-free evidence; never upload private server logs, dumps, identity pages, tokens or credentials into GitHub.

Resolve the strict native critical/high gate and independent/license review before permitting customer data or a paid pilot. The implementer cannot certify its own security review as independent. Owner approval is required for the concrete external publication/Phase 8 pilot; no such publication occurred in Phase 7.
