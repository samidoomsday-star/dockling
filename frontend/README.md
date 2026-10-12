# Dockling web frontend

**Current real app: `saas-phase-7`, including Phase 8 worker security fixes.** This React/TypeScript/Vite frontend has two explicit modes:

| Mode | Setup | Behavior |
|---|---|---|
| Real local app | [Windows guide](../docs/saas/WINDOWS-TESTING.md) / [full local setup](../docs/saas/LOCAL-SETUP.md); `npm run build:api` served by the Python API | Actual sign-in, private uploads, conversion, review/exports/removal, BYOK/model/effort setup, owner/team/account/manual-billing/operations tools |
| Separate UI demo | Node only; `npm run dev` or `run-web.bat` | Fictional interactive screens, no actual authentication or document processing |

The real app needs Linux x86_64/Python 3.12, Node 24.15+ within 24, Docker/Compose, private PostgreSQL/storage/identity and its restricted Ubuntu worker. Windows uses WSL 2 Ubuntu 24.04/Docker Desktop integration and still needs receiving-device verification. No hosting or LLM key is needed for initial real local tests. Online checkout, external email and public hosting remain unconfigured.

## Separate UI demo

An interactive, responsive **Stage B preview**, with customer self-service and owner/admin screens. Forest teal, peach, dusty blue and lavender follow the approved visual plan. This folder does not replace the Python converter.

**Everything uses synthetic fixtures by default.** No real upload/OCR, login, secret storage, model request, payment or hosting occurs. State is held in memory and resets on reload. Never select real client files or enter real keys here. Reference downloads are fixed synthetic files generated with the original Python writers; they do not reflect selected documents or UI edits.

## Run the demo on your own computer

Use the current branch; the separate demo remains available in the same clone:

```text
git clone --branch saas-phase-7 https://github.com/samidoomsday-star/dockling.git
```

Install **64-bit Node.js 24 LTS, version 24.15 or newer within version 24**, from [nodejs.org](https://nodejs.org/en/download). Version 24.19.0 was tested here. Reopen your terminal after installation. This frontend preview needs no Python, OCR models, database or API key.

On Windows, double-click **run-web.bat** in the cloned folder. It checks Node, installs locked frontend dependencies and starts the local preview in your browser. Keep its terminal open. Close it or press Ctrl+C to stop. This Windows launcher is supplied but has not been tested on an actual Windows device.

Alternatively, open a terminal in the cloned folder and run each command separately:

```text
cd frontend
```

```text
npm ci
```

```text
npm run dev -- --open
```

Use the address Vite prints in **your own local terminal**. The dev server binds to your device’s loopback interface. It is not a public staging deployment. If that port is busy, Vite prints the next available port. To preview a production build locally, run `npm run build`, then `npm run preview -- --open`.

## What to try

1. Choose **Try the guided sample**.
2. Edit the café row: change Debit from **12.59** to **12.50**. Stage the change, then **Save staged changes**.
3. Open **Checks**. Compare both rows with the source, tick them and add a note. **Record source check**.
4. Open **Exports**, prepare the preview package and download fixed reference files.
5. Explore **New conversion**, **AI connections**, **Categories** and **Settings**. AI connections support custom HTTPS URLs, manual model IDs and capability-bound effort choices. Keys and actual provider tests require the real API-mode app; the demo never handles real credentials.
6. Switch **Preview role** to **Owner / admin** to inspect profiles, pricing and health controls. This selector is not security.
7. Try **Data & privacy** removal, including the simulated partial failure and retry. Certificates clearly describe preview-only memory removal.

Reload to start over. Conversion tabs and job search/filter choices are URL-based; sample data and preferences reset. See [the coverage ledger](../docs/FRONTEND-COVERAGE.md) for all original capabilities and pending integrations.

## Development verification

From `frontend`, install the browser once:

```text
npx playwright install chromium
```

Then:

```text
npm run check
```

This runs ESLint, Prettier, TypeScript/build, adapter tests and Chromium browser journeys, including accessibility scans and small-screen checks. Linux hosts may need Chromium system libraries; use `npx playwright install --with-deps chromium` only where OS package installation is permitted. A restricted home can use `PLAYWRIGHT_BROWSERS_PATH` and npm `--cache` pointed at a writable directory. Use the same browser-cache path for installation and tests. Test artifacts stay ignored under `test-results` and `playwright-report`.

The original Python gate remains `python scripts/check.py` with the project venv interpreter. Rebuild reference downloads with `python scripts/build-web-samples.py`; the script checks four CSV goldens and uses production Excel/OFX writers. Generated assets contain fictional data only. Actual Excel/accounting import acceptance remains separate.

## Real API integration

`frontend/.env.saas` selects `VITE_APP_MODE=api`, which renders `FoundationApp` with the real authenticated APIs. The older generic `Api`/`HttpApi` interface belongs to the demo contract; it is not the current app's setup route. API failures produce errors, never demo fixtures. Session/role/revision/CSRF and financial/source/privacy checks are enforced by the server. Uploads, secrets, database/storage access and provider requests do not belong in Vite environment variables or a static client bundle.

The SaaS installer builds with `npm run build:api`; the Python API serves this bundle and refuses a demo build. **`npm run check` includes the demo build and overwrites that output.** After demo checks, run `npm run build:api --prefix frontend` from the repository root and restart the ordinary API before real browser tests or owner testing. This is required even if every demo check passes.

A static frontend host alone does not run the API, identity, OCR worker or private storage. Actual staging follows [the hosting handoff](../deploy/staging/README.md); local HTTPS rehearsal does not provision a public server. Use fictional data until security/licensing/host/field release gates are satisfied.

## Sending this to Kilo Code or another assistant

For the actual app, copy the prompt in [WINDOWS-TESTING.md](../docs/saas/WINDOWS-TESTING.md#2-copy-this-prompt-into-your-local-assistant) or [DEVICE_SETUP.md](../docs/DEVICE_SETUP.md). Those cover the current branch, API/worker setup, verification, private login and safe stop/resume.

For screens only:

> Set up the explicit UI demo on the saas-phase-7 branch of https://github.com/samidoomsday-star/dockling on this device. Read AGENTS.md, frontend/AGENTS.md and frontend/README.md. Preserve existing work/private settings. Install Node 24.15+ within 24, run npm ci in frontend and start npm run dev -- --open. Guide me through the fictional review/export journey and clearly explain that it does not process files or sign in. Do not collect keys, merge main or publicly deploy. If you run npm check, install Chromium first and restore the API build afterward if the real app is also installed. Report actual device results separately.
