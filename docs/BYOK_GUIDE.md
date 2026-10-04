# Your own OpenAI-compatible models

Dockling's normal PDF/OCR flow runs locally without an LLM key. Optional AI can propose structured rows when a supported extraction candidate needs review. It uses **your** provider, key, model and selected effort; these settings affect Dockling, not this Codex chat.

## Set up privately on your device

From the project folder in PowerShell:

```powershell
.venv\Scripts\python.exe -m stmtconv ai setup
```

The prompts ask for a nickname, OpenAI-compatible base URL (including `/v1` when required), hidden API key, provider terms confirmation, API style and JSON/effort parameter formats. Use HTTPS; localhost HTTP is supported for a local server. The provider must actually support the selected API, model and parameters. Do not paste keys here.

Choose `chat` for `/chat/completions` or `responses` for `/responses` according to provider documentation. JSON modes are `prompt_json`, `json_object` and `json_schema`; use the mode supported by that endpoint. Chat's default effort parameter is `reasoning_effort`; Responses uses `reasoning`. Some models accept neither, so choose `none` and provider-default effort.

You may discover models (a metadata request, no transaction payload) or enter the exact model ID manually. The guided picker selects the highest **known supported** effort by default. Standard `/models` responses often contain no effort information; in that case the only initial choice is `provider_default`. This does not imply Max is supported.

If your provider documents effort levels for that exact model, register only those levels. Example with placeholders—replace every placeholder and do not assume this set is supported:

```powershell
.venv\Scripts\python.exe -m stmtconv ai capabilities myprovider MODEL_ID "low,medium,high,max" "MODEL_SPECIFIC_DOC_URL"
```

Confirm that you checked the model-specific documentation. Then:

```powershell
.venv\Scripts\python.exe -m stmtconv ai pick myprovider
```

Choose the model and effort. **Max appears when provider metadata advertises it or your documented capability registration includes it.** `xhigh` and `max` are separate choices. A rejected setting fails visibly; Dockling never silently lowers effort or switches models.

`ai list` displays the selected settings without keys. `ai models myprovider` refreshes discovery; `ai test myprovider` tests model discovery/connectivity only, not paid inference or all completion parameters. A provider without model discovery may still work through manual model entry, but this metadata test will fail.

For provider-specific parameters, use `ai adapter --help`. It can explicitly set schema mode, effort style, token field (`max_tokens`, `max_completion_tokens`, `max_output_tokens`), routes and optional zero temperature. Check documentation before changing them. For a reasoning model that requires `max_completion_tokens`, set that explicitly; there is no hidden retry with different settings. Setup choices serve as adapter presets; routes and fields remain editable for compatible services.

## Consent and use for a job

Check current retention/training/data-use terms and whether your client permits this provider to receive their data. A paid plan alone is insufficient. Record actual per-order consent:

```powershell
.venv\Scripts\python.exe -m stmtconv ai-consent JOB --grant --note "Client agreed through the order message on DATE to PROVIDER/MODEL"
```

Enable AI only for the requested extraction:

```powershell
.venv\Scripts\python.exe -m stmtconv extract JOB --ai
```

AI is only called if the normal candidate needs review and safely isolated table cells are available. If there are no safe cells, it refuses rather than uploading a whole PDF/image. Unknown tables may need manual review or a profile first. The payload omits file paths, account headers and full documents, masks known names/long numeric identifiers and sends minimized row cells. Masking cannot guarantee that arbitrary free text contains no sensitive information; consent and suitable terms still matter.

Requests and invalid-output retries consume the per-order page budget **before** sending; default cap is 20 pages. API errors also consume that reserved budget. Provider/model/effort changes require renewed consent; consent renewal does not reset the budget. Inference can incur your provider's charges. Real completion calls have not been tested here; fake providers and blocked sockets cover the automated tests.

AI rows remain untrusted source data even if balances reconcile. Run `review JOB`, compare **every AI-derived row** to its original source and correct errors in the review workbook. After that source comparison:

```powershell
.venv\Scripts\python.exe -m stmtconv apply-review JOB --confirm-ai-source
```

This records source confirmation separately from manual amount fixes. It does not automatically prove the source comparison happened. Normal validation, spot-check and export gates still apply. Revoke consent with `ai-consent JOB` without `--grant`.

## Where keys live

Provider settings are saved in ignored `workspace/.ai/providers.json`, with private file/directory permissions where supported. The key is local plaintext: this is not an OS credential vault. Use an encrypted/protected device and exclude the workspace from sync/backups you do not control. Setup and logs hide keys, but do not intentionally share the settings file.

Optional `.env`/environment overrides exist for provider nickname, model, effort, API key and terms. The guided setup is easier; avoid conflicting overrides. Preserve `STMTCONV_OFFLINE=true`: that controls local extraction models; explicit `--ai` plus the gates allows the AI adapter's request. No application processing network connection occurs outside that adapter.
