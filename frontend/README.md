# Dockling web frontend

An interactive, responsive **Stage B preview**, with customer self-service and owner/admin screens. Forest teal, peach, dusty blue and lavender follow the approved visual plan. This folder does not replace the Python converter.

**Everything uses synthetic fixtures by default.** No real upload/OCR, login, secret storage, model request, payment or hosting occurs. State is held in memory and resets on reload. Never select real client files or enter real keys here. Reference downloads are fixed synthetic files generated with the original Python writers; they do not reflect selected documents or UI edits.

## Run on your own computer

Clone the frontend branch (it includes the completed Python work and design documents):

```text
git clone --branch web-frontend https://github.com/samidoomsday-star/dockling.git
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
5. Explore **New conversion**, **AI connections**, **Categories** and **Settings**. AI connections support custom HTTPS URLs, manual model IDs and capability-bound effort choices. Keys and actual provider tests require the backend.
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

## Future API integration

`Api` in `src/lib/types.ts` separates the demo store from same-origin HTTP integration. Setting `VITE_APP_MODE=api` selects `HttpApi`; a failed or malformed response produces an error, **never fixture fallback**. Any other mode value fails startup. This adapter is an integration contract, not a running backend. Real upload transport and streaming worker progress are not implemented.

The future server must implement `/api/v1/workspace`, job create/process/review/spotcheck/consent/AI-source/exports/close, connections, rules and settings. Workspace responses must match the runtime schemas and include an authenticated `X-CSRF-Token` header; mutations send it with same-origin credentials. The server must enforce authentication, authorization, CSRF, revisions, financial checks and all privacy/AI gates independently of the browser. Credentials and session tokens must not be stored in localStorage. Uploaded files and keys must never be added to Vite environment variables or the client bundle.

Stages C/D connect the existing Python services and add secure accounts/private storage/worker behavior. Stage E selects and tests hosting. A static frontend host alone does not run OCR or make this ready for real customers. Use synthetic data until those stages and real-layout/import checks pass.

## Sending this to Kilo Code or another assistant

> Set up the `web-frontend` branch of https://github.com/samidoomsday-star/dockling on this device. Read AGENTS.md, frontend/AGENTS.md, frontend/README.md and docs/DEVICE_SETUP.md. Preserve existing work and private settings. Install a compatible Node 24 LTS and run npm ci in frontend. Install Playwright Chromium, run npm run check, start the preview and guide me through the synthetic correction/source-check/export journey. Explain each owner action plainly. Do not mistake the demo for real OCR/authentication, collect my keys in the browser, merge main or publicly deploy. If I also request the existing Python converter, follow the separate device guide and verify its models/full gate/selftest. Report actual device results and unrun checks separately.
