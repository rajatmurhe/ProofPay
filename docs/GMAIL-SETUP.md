# Gmail connection setup

The connector code and mocked provider flows are tested. A successful live Gmail connection/import has not been verified. No Google credentials are bundled.

## Configure your own Google project

1. In Google Cloud, choose/create the project for ProofPay and enable the Gmail API.
2. Configure the OAuth consent screen and add your own account as a test user while the app is in testing.
3. Create an OAuth client of type **Web application**. Register this exact local callback:
   `http://127.0.0.1:3017/api/connectors/gmail/callback`
4. Add these values to the ignored server `.env`:

```dotenv
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
CONNECTOR_ENCRYPTION_KEY=your-generated-fernet-key
```

Generate the encryption key locally, then place its output in `.env` without sharing it:

```sh
.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Keep the key stable and protected outside the database. Losing it makes saved connection credentials unreadable; replacing it requires reconnecting. The current release has no automated key-rotation workflow.

## Connect and import

Restart the API, sign in, and open **Connect & import → Import from Gmail**. Choose **Connect Gmail** and review Google's consent screen yourself. ProofPay requests `gmail.readonly`; it does not request send, edit or delete access.

After Google redirects back, the screen reads connection status from your authenticated account. Select a date range of at most 31 days, check the consent box and import. Dates use India time; the Before date is excluded. Each UI batch checks up to 20 matching emails. If more match, **Import next matching emails** continues with an encrypted, account/date-bound cursor valid for 15 minutes. Changing dates starts a fresh import.

Only plain-text MIME parts are parsed. HTML-only mail, attachments, invalid or oversized content are skipped and counted. Full bodies, raw headers and irrelevant text are not retained. Gmail imports always use local rules, even when the separate AI mode is configured. Searches are limited to financial keywords; they are not a complete scan of all financial email formats.

## Disconnect

Choose **Disconnect Gmail** to remove local stored credentials and attempt Google revocation. If revocation cannot be confirmed, the app tells you to remove ProofPay from your Google Account's third-party access settings. Disconnecting preserves already imported records; **Delete my financial data** removes your structured financial records separately.

## Public use

Use HTTPS and the exact production callback matching `LOCAL_WEB_ORIGIN`. Google classifies [`gmail.readonly` as a restricted scope](https://developers.google.com/workspace/gmail/api/auth/scopes), so public rollout requires the applicable OAuth verification/security assessment. Testing-mode refresh-token lifetime and other constraints follow [Google's OAuth documentation](https://developers.google.com/identity/protocols/oauth2/). This code does not bypass Google consent, app verification or security warnings.
