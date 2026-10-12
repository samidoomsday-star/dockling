# Worker security remediation

The worker now uses a digest-pinned Ubuntu 24.04 LTS base and its vendor-maintained Python 3.12 packages. Local strict Trivy verification reports **zero high and zero critical findings** across the installed OS and copied Python runtime packages. This clears the tested worker-image advisory gate. Independent review, other deployed services, model/dependency terms, actual hosting, permitted field/import tests and the paying pilot remain separate requirements.

## What changed and why

The previous Debian 13 worker had 59 high and one critical finding, all in OS packages. Its critical finding was `libxml2` advisory `CVE-2026-6653`; the returned Debian scan reported no fixed version. A tested official Python 3.12.14 slim Debian 12 alternative was rejected: its native imports passed, but its scan found 71 high and four critical findings. The working stack was preserved during these experiments.

The accepted Ubuntu base is the official Linux amd64 image at digest `sha256:f610ab94648195aa356059f5b41d6085c9d4d903c072430cdd1af7bdb646106b`. It supplies vendor-patched Python 3.12 (the tested interpreter reports 3.12.3). The development environment remains Python 3.12 with the existing frozen dependency/model hashes; Docker supplies the worker interpreter. The copied native wheels were checked against the new runtime with actual imports, verified models and document conversion. No dependency version or model hash was changed to force a pass.

Build-time package downloads use HTTPS, the configured trusted CA bundle and normal signed Ubuntu repository/package verification. The public CA directories explicitly permit traversal by the package downloader; private application keys keep their existing permissions. An explicit APT CA path handles minimal images without an existing system certificate store. No certificate-error bypass, unsigned-package option or advisory suppression is used.

The worker remains UID/GID 1000, with read-only root/models, bounded scratch/CPU/RAM/processes, dropped capabilities and no Docker socket or arbitrary public egress. PostgreSQL role restrictions and production TLS checks remain active. Existing volumes, vault/backup material and account/job evidence are preserved.

## A scan must contain evidence

`scripts/check-worker-security.py` resolves the selected local image to an immutable image ID before scanning. It requires the report to identify that image, a supported non-EOL OS, a populated native-package inventory and Python inventory containing the core Docling/Torch/OpenCV packages. Missing or mismatched coverage is an unavailable scan and cannot clear release. Before this fix, six negative cases incorrectly passed; all eight focused regressions now pass, including the existing rule that unfixed critical findings still block.

Run the normal strict check after building:

```bash
.venv/bin/python scripts/saas-local.py worker-build
.venv/bin/python scripts/check-worker-security.py
```

An explicitly selected local candidate can be checked with `--image`. `--report-only` records development evidence and does not waive findings or missing coverage. A scan is an observed advisory snapshot for that exact image; rebuild and rescan when publishing a new image. Preserve the deployed digest and previous verified rollback image. A production rollback must also meet the current strict gate; the historically blocked Debian images are retained for development recovery, not cleared customer deployment.

## Observed local acceptance

- Native imports include OpenCV, Torch/Torchvision, PDFium, lxml, Docling and the actual worker. CPU operation passes.
- The candidate strict scan identifies Ubuntu 24.04 and inventories 145 OS packages and 145 Python packages, with zero high/critical/unfixed findings.
- All six synthetic input cases pass the genuine HTTPS worker pipeline, six writers, hashed ZIP and live removal. Raw extraction remains 15/16 rows; one known fictional scan description is corrected through review. All 16 reviewed rows match. This remains a small synthetic observation, not general accuracy or real accounting-import evidence.
- The actual HTTPS browser passes trusted TLS, rejected untrusted CA/wrong hostname, real OIDC/cookies, source review, exports, tenant privacy, removal and mobile checks.
- Complete local SaaS verification passes 164 tests; strict lint/format/types and the 150-operation/160-schema/33-feature contract check pass. [Fresh GitHub CI](https://github.com/samidoomsday-star/dockling/actions/runs/38190308098) passes at `eb5222a`: 164 SaaS/318 converter tests, genuine HTTPS and ordinary OIDC/fake-AI/account/billing/crash-recovery journeys, and encrypted isolated backup/restore/expiry. Its rebuilt worker strict coverage report also records zero high/critical/unfixed findings; exact image evidence is in `PHASE8-SECURITY-EVIDENCE.json`.

No public host, real customer document, external payment/message, paid provider request or main merge was created by this remediation. Continue with the outstanding prerequisites in [the pilot guide](PHASE8-PILOT.md).
