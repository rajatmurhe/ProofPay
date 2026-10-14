# ProofPay test results and fixes

The Phase 3 results below are the historical baseline. Current production-foundation validation is recorded in the final section.

Verified on 14 October 2026. The local app passes the automated checks below. Browser testing used a separate synthetic database; the existing app's 34 records were preserved across its API restart.

## What was checked

| Check | Result | What it confirms |
|---|---|---|
| Backend tests | 31 passed | Parsing, privacy filtering, duplicates, refunds, corrections, owner boundaries, safe uploads, retries and provider failure paths |
| Browser journeys | 5 passed | Imports, evidence, refund lifecycle, correction, review actions, filters, exports, error recovery, deletion and responsive layouts |
| TypeScript | Passed | Frontend type checking |
| Production build | Passed | Updated frontend builds successfully with webpack |
| PostgreSQL 17 | Passed | Migrations, refund journey, evidence count and replay; separate verification rows cleaned up |
| Current app | Passed | API is healthy and existing record identities are unchanged after restart |

The five browser journeys cover:

1. A ₹1,499 purchase reported by SMS and email, a pending refund, ₹499 received, ₹1,000 net purchase, field correction and repeat import.
2. Mixed synthetic demo, EML upload, private-message and OTP discard, exports, metric drill-down and mobile layout.
3. Readable quality results, card-statement and declined-payment fixes, invalid upload recovery, import feedback, deletion, and all five screens at 360 px.
4. Refund link acceptance, undo, proposal from the refund record, rejection and Escape to close the detail dialog.
5. JSON and CSV uploads, currency/source/date/search filters, CSV download, JSON export and spending totals.

Chrome tests used desktop and simulated mobile viewports at 360/390 px. Screens remain within the viewport; wide activity tables scroll within their own container. Screenshots were visually inspected. This is not a real-device or comprehensive accessibility audit.

## Problems fixed

- Amounts such as `INR 2400.` now accept a sentence-ending full stop without accepting malformed decimal precision.
- Declined and unsuccessful payment/transaction notices pass the financial relevance gate and retain their failed status.
- The explicit phrase `debit hua` is recognised; missing date and merchant details still require review.
- Refund links can be proposed from either the purchase or the refund record. Related-record choices are restricted to compatible types, and stale form choices are cleared.
- Currency selection now filters the activity list consistently with the financial summaries. Currency and source controls have explicit accessible names.
- Navigation returns to the top of the selected page. The spending chart has an amount scale and stable bars.
- Error messages explain the next action; a successful action clears a prior error, and starting a new action clears an old success notice.

## Changes for the end user

The theme now uses navy, blue and light blue inspired by the supplied image. The supplied logo is not embedded. Import results explain what was saved, already imported, skipped or failed, and offer direct activity/review actions. Quality results use readable cards and short explanations instead of raw JSON. Processing labels are clearer, and parser details are tucked into an expandable technical section.

In the app, open **Connect & import → View quality check results**.

## Evaluation results

The dataset contains 27 development cases and 50 cases that were originally held out. Known failures from the latter were inspected to fix the parser, so current runs are **regression checks, not an unseen-data accuracy estimate**. The original aggregate results are preserved in `evaluation/baseline-test-summary.json`. Labels were not changed.

| Measurement on the 50-message sample | Before fixes | After fixes |
|---|---:|---:|
| Financial messages found | 33/35 | 35/35 |
| Unrelated messages incorrectly retained | 0 | 0 |
| Amount, currency and meaning correct | 32/35 | 35/35 |
| Message category macro-F1 | 0.7641 | 1.0000 |
| Explicit event dates correct | 8/8 | 8/8 |
| Checked critical fields in complete records | 27/27 | 29/29 |
| Coverage of relevant messages marked complete | 77.14% | 82.86% |
| Duplicate matching | 2/2 | 2/2 |
| Purchase/refund matching | 2/2 | 2/2 |

Development amounts: 19/19; development dates: 10/10. Rules and synthetic fixture modes both pass the current sample. The evaluator now includes status-only and date-only mismatches in failure examples, in addition to relevance, type and amount failures. Current reports contain no failures on these samples.

These are small synthetic samples. Matching tasks have only two positive cases each. The checked-field metric does not verify every field or the authenticity of any bank/merchant message. Personal-data reliability remains unmeasured. Successful live AI calls and automatic SMS/Gmail connections remain unverified.

## Reproducing the checks

From the repository root:

```sh
PYTHONPATH=services/api .venv/bin/pytest services/api/tests -q
.venv/bin/python evaluation/run.py --split development
.venv/bin/python evaluation/run.py --split test
.venv/bin/python evaluation/run.py --split test --mode fixture
npm run typecheck --prefix apps/web
API_URL=http://127.0.0.1:8018 NEXT_DIST_DIR=.next-qa npm run build --prefix apps/web
E2E_BASE_URL=http://127.0.0.1:3018 npm run test:e2e --prefix apps/web
```

For the browser command, first run an API on port 8018 against a separate migrated database with `LOCAL_OWNER=qa-synthetic` and `LOCAL_WEB_ORIGIN=http://127.0.0.1:3018`, and serve the QA frontend build on port 3018. Browser tests delete/reseed that configured owner's records. The `.next-qa` build directory keeps the current development app separate.

Non-blocking tool warnings: installed Starlette TestClient's httpx integration is deprecated; browser tooling reports environment colour/architecture warnings. They did not cause check failures.

## ProofPay rename verification

The app branding, browser title, API title, package name, CSV filename, documentation and development database names use ProofPay. All 31 backend tests, five browser journeys, TypeScript and production build passed again after the rename. PostgreSQL was tested with the renamed `proofpay` user/database in a separate disposable local instance. The existing SQLite database was renamed with the API stopped, and all 34 record identities were verified unchanged. Screenshots were refreshed using synthetic test data.

## Production-foundation validation

Verified on 14 October 2026: **48 backend tests passed**, **five demo browser journeys passed**, and **one authenticated account browser journey passed**. TypeScript and production frontend builds passed. Migrations 0002/0003 and the account/session/CSRF/tenant smoke passed on isolated PostgreSQL 17. The local API now rejects unauthenticated financial reads, and all 34 legacy record identities remain unchanged.

New checks cover account-to-account read/export/correction/link/delete isolation; Argon2 hashes and opaque session persistence; origin/CSRF checks; session rotation, idle expiry, logout, disabled users and login throttling; production startup guards; encrypted Gmail tokens, account/session-bound state and PKCE, callback replay/expiry/wrong scope, token refresh, bounded provider responses, import privacy/idempotency, date/account-bound cursors, concurrent disconnect before retention and disconnect during pending/in-flight consent. Browser checks cover registration/sign-in, private demo data, logout, another account's empty workspace, foreign-record rejection, renewed sign-in, 401 expiry handling and desktop/mobile layouts.

Google responses were mocked in tests. No real mailbox, successful live OAuth exchange, real-message quality or public deployment was verified. Screenshots `sign-in-desktop.png`, `sign-in-mobile.png` and `gmail-setup-desktop.png` contain only synthetic test accounts. See GMAIL-SETUP.md and PRODUCTION-READINESS.md for setup and outstanding requirements.
