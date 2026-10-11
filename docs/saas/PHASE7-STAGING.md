# Staging and field validation

The app now has a separate HTTPS test environment and a repeatable way to record field results. This prepares a real server; it does not create a public URL. See `docs/tasks/saas-phase-7.md` for scope and acceptance status.

## What changed

- Production API and worker database connections verify certificates and hostnames. Identity requests and private-storage requests verify their configured CA too. Public system trust is the default; an explicit absolute PEM path supports private CAs. No insecure TLS option was added.
- A bounded read-only preflight checks configuration, vault presence, restricted database identity/current encrypted schema, private storage, live/ready responses and security headers, anonymous job/admin/bucket denial, OIDC public keys, login PKCE/callback/Secure cookie and the API UI document. Reports contain fixed status codes, not private responses. Passing always says `launch_approval: not_assessed`.
- Staging pauses AI requests independently of saved BYOK connections. Admission refuses requests before quota reservation; the dispatcher does not start or consume queued work. Customers can still configure their custom OpenAI-compatible provider, model and actually supported effort. Regular conversion/review work. A pause does not prove that an already running old process has erased memory; interrupted production cleanup remains fail closed.
- Private field observations keep permission, source accuracy, financial reconciliation, actual destination imports, review/support time and complete allocated costs separate. Unknown costs and unrun imports remain unknown. The validator checks consistency, not legal permission or the truth of recorded observations.
- Combined-image coverage uses `(source_file, physical_page)` coordinates. Virtual page 2 and a second image's physical page 1 previously disagreed after review, blocking exports. Missing/wrong sources still fail. Old combined snapshots without this inventory must be converted again and reviewed; never bypass their export gate. Single-file serialization/hashes and financial thresholds remain unchanged.

## On another computer

Use `docs/DEVICE_SETUP.md` and `docs/saas/LOCAL-SETUP.md` for everyday Windows/WSL local testing. That route needs no hosting account, LLM key or special browser certificate. Give your coding assistant:

> Read AGENTS.md, docs/DEVICE_SETUP.md and docs/saas/PHASE7-STAGING.md. Set up the real app on Linux x86_64/Python 3.12/Node 24/Docker, preserving existing configuration, vault/backup keys and volumes. Then optionally run the separate synthetic HTTPS rehearsal and acceptance checks. Keep model requests paused, use generated fictional documents and report the strict native security gate. Leave the real API-mode UI ready. Do not deploy publicly or process customer statements.

After ordinary installation and worker build:

```bash
.venv/bin/python scripts/saas-fixtures.py
npm run build:api --prefix frontend
.venv/bin/python scripts/saas-rehearsal.py setup
```

Keep this running in a separate terminal:

```bash
.venv/bin/python scripts/saas-rehearsal.py run
```

Run acceptance sequentially, without other browser/OTP/install/backup writers:

```bash
.venv/bin/python scripts/saas-rehearsal.py check
.venv/bin/python scripts/check-worker-isolation.py --rehearsal
.venv/bin/python scripts/saas-rehearsal-verify.py
PLAYWRIGHT_BROWSERS_PATH=/tmp/dockling-playwright .venv/bin/python scripts/saas-rehearsal-browser.py
```

Install pinned Playwright Chromium and its Linux system dependencies plus `libnss3-tools` first. The browser runner uses the pinned small official Python base as an empty test container, read-only mounts of the installed Node binary/Chromium/NSS tool/system libraries, current UID/GID, dropped capabilities, read-only root and bounded scratch/resources. Its host network reaches the fixed loopback app. It is a trusted synthetic browser test, separate from the restricted parser; it is not a deployment image. Only the ignored rehearsal directory is writable. It does not change HOME or the host certificate store.

Chromium 146+ uses a separate ignored XDG NSS store with only the name-constrained test CA. Node's separate request client gets that CA only inside the test command. The browser also tests an empty trust store and a wrong hostname; no certificate-error bypass is used. Direct native JavaScript execution refuses a legacy global NSS store; this cloud has one, so the container route is used. Linux x86/Debian/Ubuntu library paths are assumed. Windows/WSL and Docker Desktop host networking are documented but untested here; the receiving assistant must verify routing. Ordinary local testing does not require this optional HTTPS container route.

Host ports bind only to loopback: API 8443, identity 8444, storage 8445, database 55433. Project `dockling-staging-rehearsal` has its own DB/storage volumes, private `.staging-saas/rehearsal/` files and broker. Fictional $0 manual invoices/entitlements are setup evidence, not actual payments. Repeated tests create fresh fictional workspace scopes and preserve earlier quota/evidence records. Worker model/SQL/network/read-only/resource restrictions remain tested. The storage bridge supports the native host's TLS route; the parser has no attachment to it or public egress.

Stop the API with Ctrl+C, then:

```bash
.venv/bin/python scripts/saas-rehearsal.py stop
```

Data and keys stay. Never use `down -v`, reset quotas, delete the private directory or regenerate matched vault/database secrets to solve a failure. Test leaf certificates last seven days and the CA signing key is not retained. On expiry, stop all rehearsal writers and ask the assistant to review and replace only the TLS certificate material, preserving all matched DB/vault/identity/storage/billing secrets. This is not unattended long-lived public certificate management.

## Permitted field testing later

Real customer documents stay out of this cloud and Git. Wait for selected-host security/privacy/permission approval or an approved owner-device workflow. Use anonymous layout codes and retain permission records privately.

Copy `research/saas/field-run.example.json` into ignored private storage with mode 0600. Record raw extraction counts before corrections; compare actual dates, descriptions, signs, amounts and balances with source. Financial reconciliation alone does not certify accuracy. Separate queue wait, conversion, human review, worker peak, support time and complete allocated infrastructure/storage/provider/labor costs. Known fictional scripted corrections are not a human timing or raw-accuracy measurement.

Test each of the six outputs in its actual destination/version. A generated file is not an import pass. Passed observations require expected rows, signs, dates and duplicate checks; unrun imports stay `not_run`.

```bash
.venv/bin/python scripts/saas-staging.py validate-field-run .staging-saas/field-run.json
```

Keep the full record private. Review real provider retention/DPA/region, terms, permission and actual model capabilities before BYOK tests. Max remains available only where supported. These fictional tests incur no paid model requests.

Write monetary decimals as JSON text, for example `"0.10"`, rather than floating-point JSON numbers. The validator rejects float/bool monetary inputs; calculations use Decimal. Model-request counts are not proof of provider dollars charged.

## Requirements for a live URL

`deploy/staging/README.md` contains reviewed candidate service/proxy/config templates and target-host requirements. No host/account/domain was provisioned here. Choose region, domain, spending limit, support/contact, data retention and backup policy. A US/EU customer audience does not settle the business country or service region.

Plan Linux x86, persistent disk/models, one HTTPS API, a separately restartable worker, verified private PostgreSQL, private object storage, identity, independent backups and monitoring. Private worker-to-DB routing must preserve public egress denial. Its 4 GiB/2 CPU test limit is not a hosting capacity guarantee; benchmark actual concurrency/load/memory. The ordinary local recommendation is 8 GB Docker memory and 40 GB free disk.

Free options in `CAPACITY-AND-HOSTING.md` require current eligibility/capacity checks. Free static hosting can show the demo, but cannot run the complete OCR service. Oracle free ARM needs wheel/capacity verification; Render free services are not a durable always-on worker/database plan; Cloud Run needs a different broker deployment design. No $0 production operation is promised.

Native critical/high findings, complete dependency/model licensing, independent review, selected-host teardown/restore/load, real imports/permissions, provider/business/legal terms, contact/support and measured economics remain launch gates. `saas-ops.py` restores only the original local stack into disposable resources; it is not a staging/production backup utility. Phase 8 is an invited paying pilot after these gates and owner publication approval.

## Observed acceptance

The complete local HTTPS sweep passes all six inputs: text, different six-row text, scan, protected PDF, photo and two combined images. Each produces six hash-checked outputs, a verified ZIP and verified live removal. Cross-workspace access is denied; the viewer cannot create jobs; admin operations use real OTP/MFA. All 13 preflight checks and actual production-mode worker TLS/SQL/model/resource/public-IP/DNS restrictions pass.

Raw extraction matches 15 of these 16 fictional rows. The scan has one description mismatch, corrected through the real review API using known fictional source values. The other five inputs match their expected rows; all required summary fields are present in this successful sweep. This is not a universal accuracy figure or human-review timing. The two-image positive case is rendered at **216 DPI**. A prior **144 DPI** combined case missed the ending date and failed OFX with `OFX_SUMMARY`; this limitation remains. The API now rejects that missing summary before queuing, explains the problem, and permits other formats after normal source checks. No missing date is guessed.

The observed worker cgroup peak since start is **1546.7 MiB** for this small generated sweep. Enqueue-to-finish timings include queue wait and are not sustained-load or isolated execution benchmarks. Host/customer costs, human review/support timing, actual accounting imports and field permissions are unmeasured.

Local acceptance used worker image `a4676cd9f89382b1696c12c3c6935fd8eda50de8d16e339a045072adb6ebde5c`; it includes all conversion/TLS/export fixes. The later monetary-input guard affects only private field validation. Strict Trivy 0.75.0 on that image records **59 high / one critical / 60 unfixed**, exits 1 and blocks release. Public Python/npm advisory checks report no known advisories at the observed versions; licensing and independent review remain separate.

The real HTTPS browser journey passes trusted TLS plus untrusted-CA/wrong-hostname rejection, real login, Secure/HttpOnly cookie, paused-AI notice, source review, six exports, ZIP, tenant privacy and verified removal. Mobile axe/overflow pass. Frontend lint/format/types/build, 42 unit tests and 19 demo journeys pass. The two fourteen-screen accessibility tests previously exceeded their 30-second total budget when running concurrently with heavy checks; all assertions and deadlines are retained and browser workers now run serially. Original converter full checks pass 318 tests and nine selftest cases; Final SaaS full checks pass 153 tests, including 21 staging/field cases. Fresh GitHub results follow after push.

Failed setup attempts included test certificate file permissions, an internal storage bridge that prevented the native host route, a malformed private pause-variable prefix, a deliberately refused global NSS store, missing test-container fonts, and disk exhaustion while building a full browser image. Only disposable build cache and superseded Phase 7 images were cleaned; original credentials, volumes, models and backups remained. The small read-only browser-container approach avoids that image build. The documentation file truncated by disk exhaustion was restored and inspected. One mixed original/SaaS pytest invocation hit their known `conftest` collision; suites are run separately. Gzip preflight double-decoding and delayed missing-OFX-summary admission were reproduced with failing tests before their fixes. No failed attempt is counted as a pass.

Read `PHASE7-EVIDENCE.json` for sanitized exact observations. Previous-phase evidence in `docs/tasks/saas-phase-6.md` remains valid at its stated source. A green functional workflow cannot override the blocked native release gate.
