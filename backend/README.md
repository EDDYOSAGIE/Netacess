# Netacess backend (Django REST Framework)

Runs on SQLite with no Docker. A confirmed payment ends with a generated access code `NETACESS_<PLAN>_<16 digits>`.
There is no fiber platform connection yet; `access_codes.services.validate_code()` is ready for it.

## Run
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env            # then fill in keys
    python manage.py migrate
    python manage.py seed_plans --esp-monthly <ESP price> --esp-onetime <ESP price>
    python manage.py createsuperuser   # phone number + password
    python manage.py runserver
    python manage.py test tests

For local development, set `SMS_PROVIDER=console`; it prints OTP messages to the terminal so demos work without Termii. Full access codes remain redacted. Termii is selected with `SMS_PROVIDER=termii`.

## Production security
The `.env.example` values are for local development only. Production startup requires `DJANGO_DEBUG=0`, a unique `DJANGO_SECRET_KEY` with at least 50 characters, a public hostname in `DJANGO_ALLOWED_HOSTS`, a real SMS provider, and `DEMO_MODE=false`. With debug disabled, Django enforces HTTPS redirects, HSTS and secure session/CSRF cookies; startup fails for the development secret, localhost-only hosts, console SMS or demo OTP mode. If TLS terminates at a reverse proxy, set `DJANGO_TRUST_X_FORWARDED_PROTO=true` only when that trusted proxy overwrites `X-Forwarded-Proto` and direct untrusted access to the app server is blocked.

## Switch to Supabase (Postgres)
Set `DATABASE_URL` in `.env` to the Supabase pooled connection string, then run `python manage.py migrate`.
Nothing else changes. Use the direct (non-pooled) string just for running migrations if the pooler complains.
SQLite ignores row locks (`select_for_update`), so test concurrent payments on Postgres before launch.

## Background jobs
Set `USE_REDIS=false` to use Django's shared `DatabaseCache` and run tasks inline; after migrations, run `python manage.py createcachetable`. OTPs and throttles use Django's cache API. Scheduled SMS reminders require `USE_REDIS=true`, a configured `REDIS_URL`, and `celery -A config worker -l info` plus `celery -A config beat -l info`.

## API
| Method | Path | Purpose |
|---|---|---|
| POST | /api/auth/otp/send | Send SMS code (`phone`, `purpose`) |
| POST | /api/auth/otp/verify | Verify code (`phone`, `purpose`, `code`); signup/login also return a token |
| GET | /api/plans | Plans with NGN and ESP prices |
| POST | /api/orders | Start payment (`plan`, `provider`, `idempotency_key`) |
| GET | /api/payments/{id} | Poll status; returns the code once SUCCESSFUL |
| POST | /api/webhooks/flutterwave | Flutterwave webhook (verif-hash checked, result re-verified) |
| GET | /api/me | Profile and validity |
| GET | /api/me/codes | Access codes |
| GET | /api/me/transactions?status= | Transaction history |
| GET/POST | /api/me/notifications, /api/me/notifications/read | Notification panel |

## Admin
Staff are ordinary users with `is_staff`. Create one with `python manage.py createsuperuser` (use your phone number, e.g. +2348012345678),
then log in on the website with the SMS code. An Admin button appears in the profile and opens /admin on the frontend.
For controlled demo accounts, use `python manage.py provision_demo_staff <+234...> ...` after deployment; it creates staff-only users and prints the phone allowlist to configure. This is data provisioning, not a schema migration. See the repository `DEPLOYMENT.md` for the Render procedure.
The admin screen shows the review queue, all payments with a timeline, provider on/off switches and the audit log.
Approve, fail, refund and provider switches all require a written reason, saved to the audit log with the staff member's name.
Django's own admin at /admin on the backend (port 8000) is still available for raw data.

Staff endpoints (all staff only): `/api/admin/summary`, `/api/admin/payments`, `/api/admin/payments/{id}`,
`/api/admin/payments/{id}/action`, `/api/admin/providers/{name}`, `/api/admin/audit`. Public: `GET /api/providers`.
Renewal payment method: `PATCH /api/me` with `preferred_provider`.

## Staff alerts
When a payment is held for review, or a provider keeps failing at checkout, every staff user gets:
an in-app alert (the bell in the admin screen, which updates by itself), an email if their profile has one
(plus anything in `ADMIN_ALERT_EMAILS`), and an SMS to their phone (`ADMIN_ALERT_SMS=0` turns SMS off).
A payment still waiting after an hour triggers a reminder, then again every 6 hours (needs `celery beat`).
Alerts are sent after the database commit and can never fail or slow a payment. Emails print to the terminal until you set SMTP in `.env`.

## Needs your input
- ESP price for each plan (seed command).
- Validity of the one-time plan (assumed 30 days).
- Espees merchant wallet and API token; Flutterwave secret key and webhook hash.
- An SMS provider for OTP (also used for staff alert SMS).
- SMTP details if you want real alert emails.

## SMS and OTP
Set `SMS_PROVIDER=termii`, `TERMII_API_KEY`, and `SMS_ALLOWLIST` for demo or staging. Keep the allowlist populated with test numbers there; leave it empty only in production. `DEMO_MODE=true` adds the OTP to the send response for demo UI use, so keep it false outside demos. Termii requests use `TERMII_SENDER_ID` and `TERMII_CHANNEL`: switch from the default `N-Alert` sender by changing `TERMII_SENDER_ID` to the approved sender, and switch delivery channel by changing `TERMII_CHANNEL` (for example `dnd`). No code change is needed. To add another SMS vendor, implement the same `send(to, message)` interface in `apps/sms/providers.py` and add it to `get_provider()`; allowlist checks must remain enabled for all real providers.

OTP purposes are `signup`, `login`, `reset`, and `phone_change`. Codes expire after five minutes, allow five failed attempts, and have a 60-second resend cooldown. SMS audit rows contain no message body or OTP/access code.
