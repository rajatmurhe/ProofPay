# Run the complete local stack

Docker Compose starts PostgreSQL, a one-shot migration, FastAPI, a separate Gmail worker and Next.js. It needs no paid AI service. The web port is bound only to `127.0.0.1`; database and API ports are private to the Compose network. Application containers run as non-root users.

From the repository root:

```bash
docker compose -f deploy/compose.yml up --build -d
docker compose -f deploy/compose.yml ps
```

Open `http://127.0.0.1:3017`, create a local account and load synthetic demo data. If another ProofPay instance already uses that port, stop that instance first or change the published port and `LOCAL_WEB_ORIGIN` together. This stack has its own PostgreSQL volume; it does not migrate an existing local SQLite file.

```bash
docker compose -f deploy/compose.yml logs --tail=50 api worker
docker compose -f deploy/compose.yml down
```

`down` preserves the database volume. Do not use `down -v` unless you intend to delete this stack's data. Back up an existing database before upgrading. Migrations are gated before API and worker startup. All services must run the same source version. Next.js API rewrites are compiled into the web build, so changing the API host requires rebuilding that image.

Gmail remains disabled until `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `CONNECTOR_ENCRYPTION_KEY` are supplied through a private environment. A local test Google OAuth client uses the callback on the web origin at `/api/connectors/gmail/callback`. The UI can still demonstrate file imports and synthetic data without Google setup.

## Before public deployment

The supplied Compose file is intentionally a local development configuration: registration is enabled, the database password is local-only, and cookies use the development setting. Do not expose it to the internet unchanged.

For a selected hosting environment:

- Keep API, worker and PostgreSQL private; terminate HTTPS at a reverse proxy/load balancer serving the web app.
- Set `ENVIRONMENT=production`, `AUTH_MODE=authenticated`, `ENABLE_REGISTRATION=false`, `LOCAL_WEB_ORIGIN=https://your-domain`, and explicit `ALLOWED_HOSTS` including the actual private proxy destination host. Production startup rejects insecure settings.
- Set a strong database password through the host's secret manager; percent-encode special characters in the database URL. Keep the encryption key persistent and protected. Supply the same database/connector environment to API, migration and worker.
- Create accounts using `scripts/manage_users.py create --email ...`, which prompts for passwords. Never publish a shared real-data demo account.
- Run migrations once before rollout, verify the health endpoint, test sign-in and CSRF, exercise a real consented Gmail import/disconnect, and configure backups with a tested restore path.
- Monitor API failures, worker availability and oldest queued task. Define retention, incident response and access policies before onboarding real customers.

No public host, domain, paid AI account or real-mail OAuth configuration has been provisioned by this change. CI verifies tests/builds and Compose syntax; it is not a deployment or a live-provider certification.
