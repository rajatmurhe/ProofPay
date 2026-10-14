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

## Account security boundary

Authentication is required by default. A signed-in account selects its unique server-assigned workspace; clients cannot choose owners in headers or request bodies. Accounts use Argon2id hashes and opaque, revocable server-side sessions. Cookie values are never stored verbatim; cookies are HttpOnly/SameSite and Secure in production. Mutations require the session's CSRF token and writes are origin-checked. Session expiry and logout remove authenticated access; the frontend unmounts account data on logout or a 401 response.

Registration is an explicit local-development option and is rejected in production mode. Operator CLI actions provision/reset/disable accounts or assign legacy demo records to one rightful, otherwise empty account. Demo mode is opt-in and forbidden in production. Startup rejects insecure production combinations. These are initial controls, not a complete security/compliance assessment; financial records still need deployment-grade encryption/backups, verified onboarding/recovery and monitoring.

## Gmail connector

The read-only Google consent request uses single-use state bound to account/session and PKCE. Access/refresh tokens and OAuth verifiers are encrypted with a server-only Fernet key. Provider endpoints are fixed; requests/responses are bounded and redirects are not followed. Connection email is retained as private account metadata. Imports require an explicit date window and consent, use local rules only, and retain the same masked structured facts as file imports. Unsupported HTML-only/attachment content is counted and discarded. Next-page cursors are encrypted and bound to account, query, connection generation and expiry.

Disconnect removes local credentials before attempting Google revocation and reports inability to confirm revocation. Imported records are deleted separately. No background email polling runs. A running import checks current connection state before retaining records; records already saved before a concurrent disconnect remain. Google provider retention and OAuth verification obligations are separate from local storage controls. No successful live connection/import has been verified yet.
