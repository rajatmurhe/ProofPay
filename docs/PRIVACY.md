# Privacy and data flow

Input arrives through paste, JSON/CSV or EML → bounded in-memory parsing → OTP gate → relevance assessment → rule extraction → optional masked provider call for unresolved relevant cases → strict validation → conservative reconciliation → structured persistence.

## Retention
- Irrelevant, OTP and unresolved-relevance content is discarded. Jobs retain aggregate counts only. No sender, subject, body, input identifier, fingerprint or retry payload is written for discarded messages.
- Relevant records store allowlisted structured fields, field-level evidence, hashed source fingerprints, source type, optional receipt timestamp, job ID, parser version and mode. No full body, subject, sender or raw upload is stored in database tables.
- Long digit sequences in descriptor/correction evidence and email/UPI addresses are masked. Explicit financial amount/date values intentionally remain intact. Long numeric transaction/order references use a SHA-256-derived opaque surrogate so masking does not collapse different references to the same last four.
- Exact-input fingerprints are owner/source/source-ID/body SHA-256 hashes. They provide idempotency for retained input, not a retrieval path to bodies. Identical content with changed source identifiers can still create another evidence record; strong event references reconcile it.
- Sources remain untouched. The application does not delete messages in a phone or mailbox.
- Deletion removes the local owner's relational rows, audit trail, evidence and jobs. It is logical database deletion, not certified forensic erasure of database pages, backups or disk snapshots.

## Limits and controls
5 files, 2 MB per file, 200 messages per batch, 20,000 characters per message, 11 MB total request budget including chunked requests. Extensions choose a parser but content must satisfy that parser. EML requires valid headers and a plain-text body. HTML, attachments, remote images and links are not rendered or fetched. Quoted lines/reply tails are dropped; complex MIME/forwarding formats need more coverage.

Framework upload handling can use temporary spool files before the application reads them; uploads are closed at request completion and never kept as a source archive. No automatic retries exist because there is intentionally no retained raw input. Failed/interrupted jobs require explicit re-import. Database uniqueness and input fingerprints make this safe for already retained messages.

Validation errors return constant messages without reflected input. Batch failures store counts only. Backend access logging is disabled in startup scripts; application code does not log bodies, prompts or provider exception strings. Do not enable request/prompt tracing with personal data. Browser paste text is held in component memory until processed; successful processing clears it. Browser memory, OS swap, developer tools and third-party provider retention are outside the guarantees of this prototype.

## Optional external AI
Default is rules only. Demo fixtures are synthetic and labelled. Live mode requires server-side endpoint, model and API key configured explicitly. OTP messages never call a provider. The endpoint receives masked relevant text with no tools or browsing capability. All responses use a strict Pydantic schema and source-token checks. Timeouts, redirects, malformed responses and ungrounded amounts fall back without storing response text. Provider interpretations remain reviewable; no live-provider accuracy claim is made. Semantic validation and de-identification still need broader adversarial evaluation before personal-data use.

## Local security boundary
One environment-selected owner. No authentication, encryption at rest, tenant onboarding, public hosting, compliance certification or production security claim. Bind both services to loopback. The API ignores caller-supplied owner headers; all reads, writes, exports and deletes use the configured owner. Origin checks reduce cross-site writes but are not an authentication system. Do not expose this app through tunnels or public interfaces. Credentials belong in ignored `.env`, never `NEXT_PUBLIC_*` variables.
