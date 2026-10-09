# Synthetic capacity evidence and hosting shortlist

**Status:** Phase 0 task 0.6 completed as a measurement/selection assessment. No host has been chosen or deployed. [Full evidence](CAPACITY-EVIDENCE.json) and [scan diagnosis](SCAN-DETAIL-EVIDENCE.json) retain the failures as well as successes.

## What was measured

Ran seven synthetic input cases, each twice in its own child process, on the current Linux x86_64 cloud environment (5 logical CPUs visible; approximately 33 GiB host RAM). Used the pinned Python 3.12/Docling CPU stack, four processing threads, and approximately 699 MiB of verified model artifacts. Both parent and workers block Python socket connections; this is not proof of a kernel network sandbox.

Fixture generation happens outside the measured child. Cold/process-warm intake+extraction exclude interpreter imports/startup; subprocess wall time includes both runs and cold imports. The second run warms imports/page cache, but the current service recreates its converter per command: it does not represent a future retained-model worker. Process-tree RSS is sampled every 50 ms; Linux high-water RSS supplements it. RSS summation can double-count shared pages and sampling can miss short peaks. Filesystem figures are cumulative post-run local input/normalized/statement artifacts, not peak scratch, exports, cloud versions or backups.

| Synthetic case | Pages/run | Cold / process-warm seconds per page | Sampled process-tree peak MiB | Exact rows/run | Result |
|---|---|---|---|---|---|
| Digital separate columns | 2 | 0.168 / 0.094 | 63 | 12/12 | Pass |
| Digital larger statement | 8 | 0.089 / 0.064 | 76 | 64/64 | Pass |
| Digital credit card | 2 | 0.117 / 0.058 | 61 | 12/12 | Pass by totals |
| Digital borderless signed amounts | 2 | 0.117 / 0.065 | 62 | 12/12 | Pass through text engine |
| Scanned separate columns | 1 | 24.506 / 11.926 | 2,106 | 5/5 | Pass, source review required |
| Scanned two-page statement | 2 | 15.356 / 14.279 | 2,560 | 10/12 | Fail exact source comparison; financial numbers reconcile |
| Simulated photograph | 1 | 19.485 / 10.592 | 2,070 | 5/5 | Pass, source review required; not a real camera trial |

The targeted second run of the failed scan again found 10/12 exact rows in both modes. **The two differences are descriptions; all dates, debits, credits and balances match ground truth.** The engine reported `VERIFIED` and retained `SOURCE_CHECK_REQUIRED`. The sample proves that financial reconciliation cannot establish all text correctness. Preserve the failed benchmark; do not weaken its truth comparison or present the financial verdict as source-accuracy proof.

## Consequences for the product and next phases

- All digital cases and the single-page scan/photo cases matched ground truth in this run. This small corpus gives no universal accuracy or p95 latency claim.
- The multi-page description mismatch is a recorded Phase 2/3 acceptance issue: retain a regression fixture, show genuine source pages and every relevant OCR warning, permit correction, and distinguish source attestations from financial verdicts. Demonstrate PDF → correction → recheck → current output before presenting that layout as ready. A sampled check still cannot certify every unreviewed description.
- Trial one OCR job at a time. A **4 GiB isolated worker** is a starting experiment with headroom above the measured 2.5 GiB peak; **8 GiB is safer to evaluate** for longer documents. Neither is a validated size for all uploads. Keep the API/DB/identity services outside that worker memory allowance.
- Current runs cover at most two OCR pages. Benchmark long scans, repeated jobs, retained converters, memory leakage and forced cancellation on the actual host before setting upload/concurrency limits. Measure disk peaks and the full review/export/backup pipeline as it becomes implemented.
- The roughly 699 MiB model cache is only model weights, not container/wheels/runtime/scratch/backup size. ARM compatibility, cold image start, licensing and vendor resource limits need separate proof.

## Hosting shortlist and constraints

Official pages checked during this Phase 0 assessment; availability and terms may change. No user account, region allocation, quota or paid commitment has been verified.

| Option | Appropriate use and evidence | What still needs proving |
|---|---|---|
| Local Docker services on the owner's device | First real app tests, fully synthetic; no hosting purchase needed. React + API + DB/storage + worker can be started from documented services. | Windows/container support, actual available RAM/CPU and fresh setup; no cloud result certifies the device. |
| Oracle Always Free Ampere A1 | Candidate for free synthetic staging if eligible/available. Current official page states 1,500 OCPU-hours and 9,000 GB-hours/month, equivalent to **2 OCPUs and 12 GB** for Always Free tenancies; home-region capacity and idle reclamation restrictions apply. This is enough advertised RAM to investigate, not tested Docling capacity. | Account/region allocation, ARM Python/torch/Docling wheel support and revised locks, model performance, HTTPS/network/secrets, PostgreSQL/object storage and independent backup operations. No service guarantee assumed. |
| Render free services | Useful for static/frontend demos or constrained disposable API experiments. Official free-service page states idle spin-down after 15 minutes, 750 workspace instance-hours/month and free PostgreSQL expiry after 30 days. | A persistent OCR worker/adequate RAM/private durable objects and recoverable DB/backups need suitable paid service types or another host; free web service is not this production topology. |
| Google Cloud Run services/jobs/worker pools | Candidate for managed API and on-demand OCR, with pricing/free allowance applying to actual resource and request use. Official pricing separates worker execution and resource charging. | A deliberately supported job/worker topology, CPU/RAM/model cold starts, queue wake-up, networking, storage/database costs and billing caps. A request-billed sleeping web service must not be assumed to keep processing the DB queue. |
| Managed PostgreSQL such as Neon | Candidate for metadata storage; official plans offer a free development tier with scale-to-zero and plan-specific storage/history/compute limits. | Chosen region, pooling/transaction context/RLS compatibility, queue polling impact on billed activity, storage/quota/backup history and production recovery promise. Not a replacement for the OCR worker or private document storage. |
| Small paid always-on host plus managed PostgreSQL/private S3 storage | Simpler production candidate when budget permits; separate API/worker processes and a region chosen for the initial market. | A current vendor quote, measured capacity, isolation/updates/secrets, backup/restore/deletion and support cost. No price or provider is selected here. |

Identity shortlist: a maintained OIDC provider; **Keycloak** is an Apache 2.0 local/self-hosted candidate with additional Java/runtime/maintenance cost. Alternatively evaluate a managed OIDC service for actual data region, MFA/recovery, quotas and price. The local provider/image version and client library are selected/pinned/tested in Phase 1. Email and merchant payment providers remain unselected; the owner's business country is not yet known.

Private S3-compatible storage is an interface choice; evaluate actual provider region, version removal, encryption, credentials, operations/egress and independent backups. A free quota is not a deletion or availability guarantee. Place all selected services in the approved data location or document permitted transfers before customer intake.

## Measurable cost and capacity worksheet

Record inputs before publishing prices: jobs/month, digital/scanned page mix, upload/output bytes, retained days/versions, team seats, jobs at peak hour, allocated worker CPU/RAM, startup/per-page times on that host, parser scratch peak, storage/backups/egress rates, identity/email/merchant fees and support/review hours.

For usage-billed compute, estimate worker runtime from job startup plus measured per-page workload; multiply by allocated CPU-seconds and GiB-seconds at the vendor's actual rates. For an always-on host, record its monthly idle cost plus storage, backup and traffic. Queue capacity depends on arrival bursts and processing time, not monthly page count alone. Add retries, deletion work and monitoring overhead. BYOK charges belong to the customer's provider; our compute/storage/support cost remains.

Do not extrapolate a two-page scan into a large-page throughput/service claim without testing. No numeric monthly production cost can be responsibly fixed yet because the budget, vendor, region, quota and first-cohort size remain undecided. Prefer free synthetic staging where feasible and ask before any actual paid resource creation.

## Reproduce and compare

With the project Python environment/models installed, from repository root:

```powershell
python research/saas/benchmark.py
```

Full report defaults to `docs/saas/CAPACITY-EVIDENCE.json`. This run exits nonzero if any exact row/verdict comparison fails and preserves the report. Keep failures when comparing hosts.

Target a case without overwriting full evidence:

```powershell
python research/saas/benchmark.py --case scan-two-page --output docs/saas/SCAN-DETAIL-EVIDENCE.json
```

`--text-only` or `--case` without an explicit output writes `CAPACITY-SUBSET-EVIDENCE.json`. The helper removes temporary synthetic fixtures/workspaces on exit. It uses no real statement or provider key. Tool dependencies are pinned in `research/saas/requirements-tools.txt`; device/ARM execution is still pending.

## Official references

- [Oracle Always Free resources and current compute allowance](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Render free-service limits](https://render.com/docs/free)
- [Cloud Run pricing and worker examples](https://cloud.google.com/run/pricing)
- [Neon plan limits](https://neon.com/docs/introduction/plans)
- [Keycloak Apache 2.0 license](https://github.com/keycloak/keycloak/blob/main/LICENSE.txt)

These sources inform a shortlist, not provider selection or an approved production budget. No R2 price claim is made; its pricing page was inaccessible during this check.
