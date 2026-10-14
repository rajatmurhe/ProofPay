# API and data model

Interactive OpenAPI schema: http://127.0.0.1:8017/docs. All endpoints use the single configured `LOCAL_OWNER`; there is no selectable owner in request payloads.

| Method | Path | Purpose |
|---|---|---|
| GET | /health | Processing mode and whether provider config exists; not a live-provider success claim |
| POST | /imports | `{messages:[{body,source,source_id?,sender?,received_at?}]}`; max 200 |
| POST | /imports/files | Multipart `files`, max 5; JSON/CSV/EML |
| POST | /demo?stage=all | Synthetic fixtures; stages purchase, initiated, received, all |
| GET | /jobs | Aggregate job status/counts, newest first |
| GET | /events | Canonical projection, evidence sources, relationships, audit history |
| GET | /metrics | Per-currency totals, review count, coverage label |
| PATCH | /events/{id} | `{field,value,reason}`; merchant/category/event_date/status; audit saved |
| POST | /relationships | `{left_id,right_id,kind}`; proposes duplicate or purchase→refund link |
| PATCH | /relationships/{id} | `{status:accepted/rejected/undone}`; reversible and audited |
| GET | /export?format=json | Structured JSON (default) or spreadsheet-injection-safe CSV |
| GET | /evaluation | Saved synthetic regression report, without lengthy failure bodies |
| DELETE | /data | Deletes current local owner's records and related rows |

SMS JSON is an array of strict message objects; CSV uses the same headers. `body` is required, `source` defaults to sms; source is sms/email/paste. ISO-8601 received timestamps are optional. Unknown keys are rejected to avoid silently importing malformed data. Sample files are in `data/synthetic`.

## Persistence
`jobs`: owner, status (processing/completed/partial/failed), aggregate counts, created time.
`messages`: owner, unique owner/fingerprint, source, receipt time, job foreign key, safe evidence, mode.
`events`: owner + strict versioned `EventData` JSON payload. Payload changes are validated in the application; PostgreSQL JSON is not a substitute for Pydantic validation.
`message_events`: many-to-many evidence links.
`relationships`: owner, left/right event foreign keys, duplicate/refund kind, suggested/accepted/rejected/undone status, reason.
`corrections`: owner, event ID, before/after/reason or relationship decision, timestamp.

Accepted duplicate links form a canonical projection; original rows are never destroyed. Compatible refund progress can advance from initiated to completed. Same-reference critical conflicts remain separate and reviewable. Reference matches are scoped by owner and any available issuer/instrument evidence. Similar amount/merchant/date only suggests a match. Several explicit partial refunds can link to one purchase. Reused order references across distinct purchases are quarantined as suggestions.

Strict field contract is in `services/api/app/schema.py` and the generated OpenAPI schema. Unknown values are null/unknown, not zero or fabricated strings. Field evidence identifies observed tokens; derived merchant categories carry `curated-demo-map-v1` provenance. User correction history is separate from observed evidence and never promoted into shared mappings automatically.

Job processing is synchronous and bounded. The row is committed before processing, and progress is committed per message. A killed worker can leave `processing`; there is no durable raw-content recovery worker. Re-import is the recovery path. This is an integration boundary for a future background worker, not a claim that such a worker exists.
