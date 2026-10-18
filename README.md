# ProofPay

An evidence-backed, local financial activity prototype for imported SMS and email. Next.js + FastAPI, with PostgreSQL migrations and a SQLite quick start. Authentication and Gmail connection foundations are available on the production-foundation branch. No public deployment or successful live inbox verification is claimed.

## Start locally

Requirements: Python 3.11+, Node 20.9+ (Node 24 recommended), npm. Use the same Node architecture for install and run; mixing Intel and Apple Silicon installations can break native CSS/compiler dependencies.

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r services/api/requirements.lock
npm ci --prefix apps/web
cp .env.example .env
./scripts/start-api.sh
```

In another terminal, from the repository root:

```sh
./scripts/start-web.sh
```

Open **http://127.0.0.1:3017**. API: **http://127.0.0.1:8017**; interactive API docs at `/docs`. Ports are chosen to avoid another app already using port 8000 on the development machine. The API script applies migrations before starting. Keep development services local. Production mode requires authenticated access, HTTPS, PostgreSQL, explicit allowed hosts and self-registration disabled. See [production readiness](docs/PRODUCTION-READINESS.md).

Create a local account and sign in, then go to **Connect & import → Load synthetic demo**. Or run `./scripts/seed.sh`. The demo contains 40 synthetic messages and uses labelled fixture mode. Import formats and samples: `data/synthetic/demo.json`, `sample.csv`, `purchase.eml`.

### PostgreSQL

```sh
docker compose up -d db
```

Set this in your ignored `.env`, then restart `start-api.sh` (which migrates the chosen database):

```dotenv
DATABASE_URL=postgresql+psycopg://proofpay:local-development-only@127.0.0.1:5437/proofpay
```

The bundled password is intentionally a local demo credential, not suitable for production. SQLite data is not automatically copied to PostgreSQL; re-import the synthetic demo. `docker compose stop` stops the local database and preserves its volume.

### AI modes

- `PROCESSING_MODE=rules`: default; deterministic extraction, no provider calls.
- `/demo`: explicit synthetic fixture path through the deterministic parser, records marked `fixture`. It does not fake live AI responses.
- `PROCESSING_MODE=live`: requires `AI_BASE_URL` (HTTPS OpenAI-compatible endpoint root), `AI_MODEL` and `AI_API_KEY` in the server environment. No model ID is assumed. Only unresolved, relevant content is eligible. Missing credentials/errors fall back to rules and increment the job's provider-failure count. OTP never reaches the adapter. Live candidates remain reviewable.

No successful live provider call has been made or claimed. An API account/key is separate from a chat subscription. Never put secrets in `NEXT_PUBLIC_*` variables. Both `.env` and databases are gitignored.

## What works

- Paste, strict SMS JSON/CSV, and plain-text EML import; bounded files/batches; aggregate processing jobs.
- OTP/relevance filtering, no raw body database retention, minimal masked evidence.
- Required message classes, explicit amount roles/dates/currencies, missing fields and quality states.
- SMS/email event reconciliation, reversible duplicate/refund links, multiple partial refunds, conflicting references and possible matches.
- Overview with traceable totals; activity search/type/source/date filters and CSV/JSON export; attention workflow; statement/refund screens; audited field corrections; local data deletion.
- The golden journey: INR 1,499 purchase in two messages → refund initiated without reducing net → INR 499 received → INR 1,000 net purchase. Sources remain inspectable; replay is idempotent.

## Verify

```sh
PYTHONPATH=services/api .venv/bin/pytest services/api/tests -q
.venv/bin/python evaluation/run.py --split development
.venv/bin/python evaluation/run.py --split test
.venv/bin/python evaluation/run.py --split test --mode fixture
npm run typecheck --prefix apps/web
npm run build --prefix apps/web
```

With separate isolated QA services running:

```sh
E2E_BASE_URL=http://127.0.0.1:3018 npm run test:e2e --prefix apps/web
E2E_BASE_URL=http://127.0.0.1:3019 npm run test:e2e --prefix apps/web -- accounts.spec.ts
```

The first suite requires a demo-mode QA API; the account journey requires an authenticated QA API with development registration enabled. Neither command should target personal-data workspaces.

Browser tests use installed Google Chrome and delete/reseed the configured owner's data. This verification used a separate SQLite database and app at port 3018, selected with `E2E_BASE_URL=http://127.0.0.1:3018`. For separate QA services, set API `LOCAL_WEB_ORIGIN=http://127.0.0.1:3018`, a separate `DATABASE_URL` and `LOCAL_OWNER`; build the web app with `API_URL=http://127.0.0.1:8018 NEXT_DIST_DIR=.next-qa`, and serve it on port 3018. Do not run them against personal data. Adjust `apps/web/playwright.config.ts` to use a separately installed Playwright Chromium if Chrome is unavailable. Tests check `/health` for the expected single-user app before deletion.

Backend tests use isolated SQLite databases. PostgreSQL smoke test: `DATABASE_URL=... .venv/bin/python scripts/verify_postgres.py` after migrations; it uses a separate synthetic owner and cleans up its rows.

Production build uses webpack to avoid the observed local native-module resolution issue. `npm run start --prefix apps/web` serves the built frontend on port 3017; the API must still run. No production deployment is included.

## Actual verification and evaluation

See the [verification report](docs/VERIFICATION.md) and machine-readable [rules regression report](evaluation/report-test-rules.json). The dataset contains 77 labelled cases in family-disjoint development/test splits. The original test sample has now been inspected to fix bugs and is a regression benchmark. [Pre-fix results](evaluation/baseline-test-summary.json) are preserved. Rules and fixture modes are evaluated separately and have identical deterministic semantics.

Current synthetic regression sample (50 inputs): **35/35** financial messages found, **0** unrelated messages retained, **35/35** amount/currency/role sets correct, **8/8** labelled event dates correct, and classification macro-F1 **1.0000**. Checked fields in complete records: **29/29**, covering **82.86%** of relevant examples. Duplicate and refund matching each contain only **2** positive cases. These results measure a small, previously inspected sample; they do not establish real-world accuracy. No personal-data evaluation or successful live AI call is verified. In the app, go to **Connect & import → View quality check results** for a readable explanation.

## Project guide

- [Product specification](docs/SPEC.md)
- [Architecture decisions](docs/ARCHITECTURE.md)
- [Data model, API and import formats](docs/API.md)
- [Metric definitions](docs/METRICS.md)
- [Privacy and retention boundaries](docs/PRIVACY.md)
- [Known limitations and prioritised backlog](docs/BACKLOG.md)
- [Five-minute demo script](docs/DEMO.md)
- [Implementation plan and decisions](docs/IMPLEMENTATION.md)

This is a useful prototype with deliberately visible limitations, not a complete financial ledger. Verified identity onboarding/recovery, live Gmail verification, consented real-data evaluation, broader multilingual parsing, full-field correction and deployment hardening remain next-release work.

## Accounts and Gmail

The default API mode now requires sign-in. `ENABLE_REGISTRATION=true` permits local development account creation; production mode refuses that setting. An administrator can provision/reset/disable accounts with `./scripts/manage-users.sh`. Passwords are entered through a hidden prompt, never command-line arguments.

Existing single-user demo records remain preserved but are not automatically exposed to newly registered accounts. An operator can explicitly assign that workspace to an otherwise empty account with `./scripts/manage-users.sh adopt-demo --email you@example.com`; this preserves record IDs and import fingerprints and revokes old sessions.

Gmail uses a separate read-only Google OAuth consent flow, per-account encrypted token storage and user-triggered bounded imports. It needs your Google Cloud OAuth configuration before activation. See [Gmail setup](docs/GMAIL-SETUP.md). The connector currently imports plain-text email parts, including nested MIME; HTML-only mail and attachments are skipped with aggregate counts. Gmail imports always use local rules.

## AI evaluation and durable imports

The portfolio upgrade adds a reproducible local TF-IDF/logistic-regression experiment, rules/LLM/hybrid evaluation tooling, a durable Gmail import worker, container setup and CI. No paid AI provider is needed for the local experiments. The classifier remains experimental and does not update financial records; live LLM evaluation remains unrun until configured.

- [Results, reproduction commands and interview walkthrough](docs/AI-AND-AUTOMATION.md)
- [Full local stack and deployment handoff](deploy/README.md)
- [Passed checks and remaining verification](docs/UPGRADE-VALIDATION.md)
- [Classifier report](ml/reports/classifier-report.json)
- [Extraction comparison report](evaluation/reports/extraction-comparison.json)

After applying migrations, start `./scripts/gmail-worker.sh` alongside the API and web app for background Gmail imports. The UI reports queued/running/completed work and the last successful import. Google OAuth setup is still required for real mail.
