# Limits and next release

## Current limitations
- Single local user, no real authentication. No public deployment or production security/compliance claim.
- Template coverage remains narrow. Sentence-ending amount punctuation, declined payments and the explicit Hinglish phrase `debit hua` are fixed. Broader multilingual parsing remains unsupported. The original sample now serves as a regression benchmark; pre-fix results are preserved in `evaluation/baseline-test-summary.json`.
- 77 labelled evaluation cases, not 500–1,000; 40 additional demo messages. The small sample cannot establish a 99% population-level guarantee. No consented real data or live-provider evaluation.
- Strict live API adapter implemented and failure-tested, but no credentials/provider run. Candidate semantics need stronger field-by-field entailment; live suggestions remain needs review, and completed-purchase/received-refund summaries exclude them.
- No Android/iOS inbox access, Gmail OAuth, bank connections, payment initiation, PDFs/images, chatbot, savings comparison or verified benefits catalogue.
- Explicit event dates support ISO YYYY-MM-DD only. Other date formats remain missing. No automatic timezone inference.
- Multiple events require explicit `||` or `EVENT:`/bullet separators. Arbitrary paragraph-level multi-event extraction is not solved.
- One occurrence can retain extra evidence when re-imported with changed source IDs. Exact input replay is idempotent; weak similarities are suggestions, not automatic merges.
- Reference collisions and last-four ambiguity cannot be universally resolved. Instrument identity stays unresolved. Order-reference ambiguity is quarantined. Refund over-allocation is flagged; it requires user correction.
- Correction UI supports merchant, category, date and status, plus reversible links. It does not yet edit every money/entity field or provide user-defined mapping rules. Delete/re-import corrected structured source data for unsupported fields.
- Bill totals are reported statements, not tracked settled balances. No full outstanding obligation ledger. Category mapping is a small versioned in-process catalogue, not a learned or shared user-correction cache.
- Synchronous batches and database aggregate jobs, not resilient background workers. Interrupted jobs can remain processing until manual re-import; no raw retry queue exists.
- Logical deletion does not scrub disk free pages/backups. Temporary multipart spooling, OS memory/swap and browser developer tools are outside retention guarantees.
- Source dates/amounts/references have minimal field evidence. Type/status/effect inference is explained by parser version and validation, not a comprehensive token-span attribution system.
- UI browser tests cover critical paths, not an exhaustive accessibility/security audit. All frontend data is local-session data; no accounts or tenancy UI.

## Priority order
1. Expand consented, redacted, family-separated evaluation; establish new unseen holdouts before improving parser breadth. Add independently annotated dates/entities/statuses and larger reconciliation ground truth.
2. Strengthen relevance gating for novel bank/card messages; robust money punctuation, multilingual parsing, richer evidence spans and explicit user approval of uncertain semantics.
3. Expand correction actions to amounts/currency/entities; introduce resolved instrument ownership, transfer pairing, settled bill state and conflict-resolution workflows with audit.
4. Authentication, real per-user authorization, encrypted storage, rate limiting, threat modelling, backup/deletion policies, audit/monitoring without message bodies, deployment hardening.
5. A safe cancellable background import worker storing only already-filtered structured work; recover stale jobs without retaining disallowed raw input.
6. Verify a configured AI provider on unfamiliar relevant messages, measured usage/latency, refusal/injection cases and robust schema/grounding. No dependency on a ChatGPT subscription.
7. Approved live connectors. Android SMS access requires explicit consent and applicable platform/store permissions; Gmail requires OAuth scopes, verification and operational review. iOS does not offer general unrestricted inbox access. Interfaces alone are not integrations. Validate current official platform requirements before implementing.
8. Broader multilingual formats, merchant mapping lifecycle, more robust instrument resolution, then a sourced/dated benefit catalogue. Keep hypothetical estimates apart from realised financial outcomes.
