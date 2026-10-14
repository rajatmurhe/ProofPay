# Production foundation: accounts and Gmail

This branch starts production readiness; it is not a production release. The Phase 3 submission remains the snapshot on `main`. No hosting or personal Google account has been connected during development.

## Implemented

- Required sign-in by default. Accounts have separate server-assigned workspaces. Caller-supplied owner IDs never select a workspace.
- Argon2id password hashing (64 MiB, three passes, one parallel lane), bounded credentials and generic login failures. Passwords, cookies and provider errors are not logged/reflected.
- Random server-side sessions with only token hashes persisted, HttpOnly/SameSite cookies, seven-day absolute and thirty-minute idle expiry, rotation at sign-in, and logout/revocation.
- Session-bound CSRF headers for writes, exact web-origin checks, trusted hosts, database-backed login/account-creation limits and no-store private API responses.
- Account provisioning, password reset, disable and explicit legacy-demo adoption through a local operator CLI. No automatic first-user claim of historical data.
- Production startup refuses demo mode, HTTP origin, SQLite, wildcard/missing hosts or enabled self-registration. Development remains loopback-only. Cookies are Secure in production and use the __Host- prefix.
- Gmail consent: read-only scope, ten-minute single-use state bound to the signed-in account/session, PKCE, fixed Google URLs, encrypted access/refresh tokens and bounded HTTP responses.
- User-triggered Gmail imports: 1–31 day windows in India time, up to 50 messages per API request (20 in the UI), plain-text MIME only, quoted replies removed, local rules only and masked financial evidence retained. Encrypted next-page cursors bind account, connection generation, date query and expiry.
- Disconnect deletes local credentials and pending OAuth state first, then attempts provider revocation. A revocation failure is reported explicitly; already imported financial records remain until separately deleted.

## Local accounts

Set these in the ignored `.env` before restarting the API:

```dotenv
ENVIRONMENT=development
AUTH_MODE=authenticated
ENABLE_REGISTRATION=true
ALLOWED_HOSTS=127.0.0.1,localhost
LOCAL_WEB_ORIGIN=http://127.0.0.1:3017
```

Open the app and choose **Create a local account**. Development email addresses are not verified. For operator provisioning without browser registration:

```sh
./scripts/manage-users.sh create --email you@example.com
./scripts/manage-users.sh reset-password --email you@example.com
./scripts/manage-users.sh disable --email you@example.com
```

The script prompts for passwords without echoing them. Reset/disable revoke sessions and pending Gmail consent state. Disabling an account does not itself revoke its Google grant; plan operator revocation before offboarding.

Existing 34 demo records are preserved under the legacy workspace. To explicitly assign it to an otherwise empty account:

```sh
./scripts/manage-users.sh adopt-demo --email you@example.com
```

This changes only the server-side workspace assignment, preserving record IDs and fingerprints. It refuses already assigned legacy workspaces and accounts with existing financial records, and revokes prior sessions. Do this only for the rightful owner of those local records.

## Required before public release

1. Google OAuth setup and an actual consent/import/revocation test. Public use of `gmail.readonly` needs the relevant Google verification/security review.
2. Verified account onboarding, safe recovery, MFA or managed identity, and an operational policy for account disable/deletion and grant revocation.
3. PostgreSQL operations, HTTPS/reverse-proxy configuration, secret manager/key rotation, encrypted financial-data storage and backups, restore/deletion procedures, abuse monitoring and security review.
4. Broader consented real-message evaluation and an untouched holdout. The existing synthetic regression scores do not establish personal-message accuracy.
5. Full CSP/nonce review, dependency/security audit and broader accessibility/device testing.
6. Import cancellation and locking under real concurrent workloads; the current connector is synchronous and checks connection state before retention. Concurrent disconnect after retention starts cannot erase already saved records.
7. HTML-only email support, broader financial wording/date formats and an explicit approval policy before any personal Gmail content is sent to an AI provider. Current Gmail imports never send content to AI.

Startup guards and tests are useful controls, not certification or permission to publish this branch as production-ready.

## References

Password/session choices follow [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) and [CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html). Gmail uses Google's [web-server OAuth flow](https://developers.google.com/identity/protocols/oauth2/web-server), [scope documentation](https://developers.google.com/workspace/gmail/api/auth/scopes) and [date-filter rules](https://developers.google.com/workspace/gmail/api/guides/filtering).
