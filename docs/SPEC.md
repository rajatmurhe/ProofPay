# ProofPay

Turn imported financial SMS/email into evidence-backed activity. Messages are evidence; events are financial facts. The local prototype supports file imports and paste, not live inbox access. Discard irrelevant/uncertain/OTP input in memory. Persist only structured facts and allowlisted masked field evidence. Purchase/refund net spend is distinct from cashflow. Card repayments never add purchase spending.

## Architecture
Next.js UI → same-origin server proxy → loopback FastAPI → SQLAlchemy → PostgreSQL (or local SQLite). Bounded imports run in request process; jobs persist only anonymous counts/status. Interruption requires explicit re-import and is idempotent. No task engine, no raw upload storage. Alembic owns tables.

## Domain
Owner-scoped jobs, messages, events, message/event links, relationships and corrections. A message may link to multiple events; an event may have multiple messages. Event payload uses strict Pydantic schema: class/subtype/status, money roles, currency, direction/effect, merchant/intermediary/issuer/instrument, explicit dates, references, observed field evidence, missing fields, conflicts and quality. Relationships are independently reversible and preserve original event/evidence. Conflicting same-reference records remain separate and flagged.

## Golden acceptance
SMS + email purchase INR 1499 with same reference → one purchase with two evidence sources. Refund INR 499 initiated → pending only. Same refund credited → received 499; net purchase 1000. Re-import does not create retained records. OTP and irrelevant text never enter database.
