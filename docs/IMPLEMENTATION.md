# Implementation plan

Repository inspected 2026-10-14: initially empty, no applicable repository instructions or code. Local prototype remains unpublished; no user accounts or agents were used.

1. **Foundation — complete:** strict schemas/migration, bounded SMS JSON/CSV, EML and paste adapters, in-memory privacy gate, masked field evidence, deterministic extraction, import/results/record UI, 40 synthetic messages and verified ₹1,499 → ₹499 → ₹1,000 journey.
2. **Financial intelligence — complete for this prototype:** all ten required message classes, rules/fixture/live provider modes, schema and evidence checks, conservative duplicate/refund relationships, conflicts, field corrections, synthetic regression evaluation. Limits are measured and documented. Live provider success remains unverified.
3. **Product — complete for this prototype:** overview, financial activity, bills/refunds, needs attention, import, safe export, filters, evidence detail, corrections/undo, accessible responsive presentation and critical browser journeys.
4. **Hardening/docs — complete for local prototype:** 31 backend tests, five browser journeys, TypeScript and production build, PostgreSQL 17 migration/golden path, owner-scope/deletion/privacy/upload/retry checks, regression reports, setup/API/privacy/metrics/architecture/limits/demo docs. Live provider, real connectors, authentication and production exposure are out of scope.

Decisions: Next.js + FastAPI; SQLAlchemy JSON payloads with owner-scoped relational evidence/event links and Alembic migrations. PostgreSQL is available through Docker; SQLite is zero-service quick start. Integer minor units for money. Unknown facts remain null. One configured local owner. Rules first and explicit fixture mode; optional server-side AI only when configured. No raw-message retry queue. Bounded imports run synchronously and persist aggregate job status.

Known verification warning: Starlette TestClient reports a non-blocking `httpx` integration deprecation. Known punctuation, decline and explicit Hinglish failures were fixed. The original test sample is now a regression benchmark with preserved pre-fix results; it must not be described as unseen-data accuracy. See `docs/VERIFICATION.md` and `docs/BACKLOG.md`.

Product refinement: navy/blue theme inspired by the supplied colours, readable import outcomes and quality cards, clearer extraction labels and technical details, amount scale on the spending chart, navigation scroll reset, consistent currency filters and purchase/refund proposal from either record. The supplied logo is not embedded.

Production-foundation branch: private accounts and revocable sessions now protect financial routes; workspace assignment is server-side, with optional operator adoption of legacy records. Gmail OAuth/import/disconnect, encrypted credentials, bounded/cursored local-rule imports and setup screens are implemented and mock-tested. Validation: 48 backend tests, five demo browser journeys, one account journey, TypeScript/build and PostgreSQL migration/security smoke. No public deployment or live Gmail success is claimed.
