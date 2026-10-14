# Drive upload checklist

The attached ProjectPlan PDF is the plan and its initial status, dated 14 October 2026. Keep it as the original planning document. Its page 3 says “Phase 1 is in progress” and “Phases 2 to 4 are not started”; that was the status when the plan was written. Attach the final verification report separately to show what was completed afterward.

## Upload these

1. `ProjectPlan-Rajat.pdf` — planning document, unchanged.
2. `ProofPay-Project-Submission.zip` — complete source snapshot with code, lockfiles, migrations, tests, synthetic sample data, evaluation results, screenshots, setup instructions and documentation. No installed dependencies, local financial database, credentials, Git metadata or test caches are included.
3. Optional separate preview: `docs/screenshots/overview-desktop.png` (or mobile screenshot).
4. Optional separate evidence: `docs/VERIFICATION.md` and `evaluation/report-test-rules.json`.

If the Drive accepts folders, upload the whole source directory instead of the ZIP. Do not upload only `main.py`; the frontend, API, migration, datasets and lockfiles are needed to reproduce it.

## What to tell your reviewer

Suggested description:

> ProofPay local prototype. I completed the Phase 1 import-to-record journey and verified the ₹1,499 purchase with duplicate SMS/email evidence, an initiated ₹499 refund, and the later ₹499 credit that brings purchase-linked net spending to ₹1,000. Re-import is idempotent; OTP, irrelevant and unresolved-relevance messages are discarded without storing their text. The upload includes the runnable source, migrations, tests, synthetic fixtures, setup guide and verification report. The original project plan remains attached as the planning baseline; later work and the measured evaluation results are documented separately. Live inbox connections and a successful live AI provider run are not claimed.

Only add “completed in one hour” if that is an accurate record of your actual work time. The repository and plan can show deliverables and test results, but they cannot independently prove the hours spent. The current code goes beyond the PDF's Phase 1 scope, so avoid saying that all of the current application was produced within the first hour unless that is true.

## Source locations inside the project

- Frontend and browser tests: `apps/web/`
- API, schemas, parsers and privacy gate: `services/api/app/`
- Database migration: `services/api/alembic/`
- Backend tests: `services/api/tests/`
- Synthetic messages: `data/synthetic/`
- Evaluation dataset, runner and actual reports: `evaluation/`
- Reproducible setup and demo: root `README.md` and `scripts/`
- Phase 1 acceptance mapping: `docs/VERIFICATION.md`
- Privacy, data model, metrics, architecture, limitations and demo notes: `docs/`
