# Upgrade validation — 18 October 2026

Source branch: `codex/ai-evaluation-and-automation`, based on `production-foundation`.

## Passed

- Backend and ML suite: **57 tests passed**. Covers existing extraction/account/privacy behavior and new split-leakage, provider-budget, grounding, queue isolation, retries, expired leases, logout/disconnect and deletion checks.
- Targeted queue and ML rerun: **9 passed** after experiment-report refinements.
- Next.js production build, including TypeScript checking.
- Browser checks: **2 passed**, covering private accounts/session handling and queued Gmail progress, navigation recovery, completion counts, date restoration and consent reset. Connector responses in the Gmail browser test are mocked.
- PostgreSQL: API, migration and worker images built; fresh migrations completed; API health check passed. A smoke test using the real migrated PostgreSQL database and mocked Google exercised enqueue, worker completion, duplicate replay, last-success status and data deletion.
- SQLite: fresh upgrade through migration `0004`.
- Compose configuration validation.
- Worker `--once` returns a nonzero exit with a sanitized message when the database cannot be opened.
- Report generation: classifier and rules extraction reports reproduced; LLM and hybrid correctly marked not run without provider setup.

The local browser run used cached Chromium Headless Shell because installed Chrome timed out at launch. After switching from x86 Node to native Apple Silicon Node, dependencies were reinstalled with `npm ci` so native CSS modules matched the runtime. These were environment issues; no browser assertion was bypassed.

## Remaining verification

- Docker stopped during the Node base-image download. The **web image and complete five-service stack have not passed an end-to-end container check**. The source web production build passed locally. Retry `docker compose -f deploy/compose.yml up --build -d` when Docker is available.
- No live Google OAuth consent/mailbox test, live LLM call, public deployment, backup restore exercise or production load test was performed.
- GitHub Actions configuration is included; local passing checks do not establish a remote Actions result.
- Classifier metrics come from a small synthetic corpus. They do not establish real-mail accuracy or production readiness.

## Re-run browser checks

Start an authenticated API with registration enabled against a disposable local database, and serve the web app with a matching API URL and origin. Then, from `apps/web`:

```bash
npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:3017 E2E_BROWSER_CHANNEL=chromium npm run test:e2e -- tests/accounts.spec.ts tests/gmail-jobs.spec.ts
```

`E2E_BROWSER_EXECUTABLE` optionally selects an already installed browser executable. Keep the API's `LOCAL_WEB_ORIGIN` consistent with the actual web port. Use synthetic accounts; these browser tests create local accounts and write screenshots.

The new [Gmail screenshot](gmail-queue-demo.png) shows a **mock connector response** with synthetic data, not live Gmail access.
