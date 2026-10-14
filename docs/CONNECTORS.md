# Future source adapters (not connected)

`InputMessage` is the canonical adapter output. A future connector should stream one bounded message into the existing in-memory gate, using a stable source identifier and explicit source receipt time. Do not write fetched raw content to a queue before relevance/OTP decisions. Retained-message fingerprints can support replay. Source deletion is never part of this product.

## Android SMS
No Android application or permission request is implemented. Reading SMS requires explicit platform permissions and a distribution-policy review. Android's default-handler guidance requires requesting the relevant default role before restricted SMS permissions in that flow; Google Play also documents limited permitted uses/exceptions and declaration requirements. A finance use case is not automatic approval. Confirm the applicable pathway before designing a live adapter. Sources: [Android default-handler permissions](https://developer.android.com/guide/topics/permissions/default-handlers), [Google Play SMS permission policy](https://support.google.com/googleplay/android-developer/answer/10208820?hl=en).

## Gmail
No OAuth client, tokens, account access or verified integration exists. A future adapter needs explicit user consent, the minimum suitable Gmail scopes, token storage/revocation, incremental sync, rate/error handling and scope verification. Restricted-scope verification and potentially security assessment depend on scope, app distribution, exceptions and server handling. Sources: [Google restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification), [OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies).

These are future dependencies, not legal approval or evidence that a live connector works. Recheck official requirements at implementation time.
