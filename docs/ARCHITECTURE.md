# Architecture decisions

1. **Reuse:** repository was empty. No previous implementation or applicable repository AGENTS instructions existed. Next.js subsequently generated its framework AGENTS guidance; bundled installation/client-component docs were consulted.
2. **Stack:** Next.js 16, React 19, Tailwind 4, Recharts (one purchase timeline), Lucide icons; FastAPI, Pydantic, SQLAlchemy, Alembic. Exact resolved versions are locked. Versions were checked against official Next.js installation documentation and FastAPI release notes. No trained classifier is justified by this small synthetic dataset.
3. **Local scope:** fixed owner, loopback-only services. PostgreSQL 17 through Compose is the documented primary store; SQLite is a zero-service quick start and unit-test backend. No public deployment, purchased services, live inbox connection or user account access.
4. **Evidence model:** original event rows + reversible relationship graph. Canonical projections preserve all source evidence. This is simpler to undo than destructive event merges and accommodates partial refund progress. Corrections to a canonical group apply to group members with an explicit audit record.
5. **Jobs:** database-backed aggregate status; bounded synchronous batches rather than Redis/Kafka. No raw message queue. The UI awaits batch completion and refreshes the persisted summary. No background worker or live streaming progress claim.
6. **Privacy:** discard OTP/irrelevant/uncertain input before persistence; no raw body archive. Only explicit financial evidence is retained. Provider integration is server-side and optional; untrusted message text has no access to tools, browsing or execution.
7. **Mode labels:** `rules` is real deterministic extraction. `/demo` uses synthetic fixtures through those rules and records `fixture`. `live` requires endpoint/model/key; only unresolved relevant cases call it. No fixture is a claimed provider response.
8. **Uncertainty:** no currency guessing, no date substitution, no automatic account ownership or merchant-from-gateway inference. Critical missing/conflicting fields prevent automatic validation. Quality labels are heuristic workflow states, not calibrated probabilities.
9. **Scope choices:** no benefits catalogue, savings comparison, secondary decorative charts, live connectors, trained model or 500 repeated templates. The shipped dataset has 40 demo inputs and 77 independently labelled evaluation cases (27 development / 50 originally held-out, now regression after debugging), designed to expose failure modes. Broader consented evaluation remains necessary.
10. **Build:** webpack is explicitly used for reproducible local builds after a machine-specific mixed Intel/Apple Silicon Node installation exposed native-module problems. Use one Node architecture consistently for `npm ci` and startup. No machine-specific binary package is a direct project dependency.

Sources for dependency baseline: https://nextjs.org/docs/app/getting-started/installation and https://fastapi.tiangolo.com/release-notes/ . Lockfiles are the reproducible version authority for this prototype.

## Diagram

See [`architecture.mmd`](architecture.mmd) for the implementation architecture in Mermaid source. It distinguishes input adapters, in-memory privacy filtering, extraction modes, persistence, reversible relationships and development-only evaluation.
