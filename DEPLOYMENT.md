# Demo Deployment: Vercel and Render

This setup deploys the Next.js frontend to Vercel and the Django API to Render. It is for a controlled live demo, not a public launch. Render uses PostgreSQL, runs migrations before deploy, serves Django static files, and checks `/health/` before routing traffic.

## Render API

1. Push the repository to a Git provider and create a Render Blueprint from the repository root. Render reads `render.yaml` and creates the API service and PostgreSQL database.
2. Set `DEMO_PHONE_ALLOWLIST` in the Render service to comma-separated Nigerian test phone numbers in international format, for example `+2348012345678`. Demo OTP codes are returned only for these numbers. Do not use real customer numbers.
3. Generate a Fernet key for `ACCESS_CODE_ENC_KEY` with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and save it in Render. Keep this key stable; changing it makes previously encrypted access codes unreadable.
4. Add Flutterwave **test** secret and webhook keys to Render. Keep Espees checkout disabled until its confirmation flow is enabled and tested.
5. After Vercel creates the frontend URL, set Render `FRONTEND_URL` to that exact origin, without a trailing slash.

`DJANGO_DEBUG` remains off on the demo service. The console SMS provider is allowed only because `DEMO_MODE=true`, and the API refuses numbers outside `DEMO_PHONE_ALLOWLIST`. This returns OTPs in API responses and is strictly a demo mechanism. For a real launch, turn demo mode off and configure a real SMS provider and the approved sender details.

## Vercel Frontend

1. Import the same repository into Vercel.
2. Set the project Root Directory to `frontend`; keep the Next.js framework preset and default `npm run build` command.
3. Set `BACKEND_URL` to the Render API origin, such as `https://netacess-demo-api.onrender.com`, with no trailing slash. This is a server-side rewrite destination; do not prefix it with `NEXT_PUBLIC_`.
4. Deploy. The browser uses the Vercel origin for `/api/*`; Next forwards those requests to Render, so a separate browser CORS allowlist is not needed.

## Demo Smoke Tests

After both services are deployed:

1. Open `https://<render-service>.onrender.com/health/`; expect `{"status":"ok"}`.
2. Open the Vercel site, load plans, and verify signup requests an OTP for a number in `DEMO_PHONE_ALLOWLIST`.
3. Confirm the OTP appears only for an allowlisted demo phone; a different phone must receive an error and no code.
4. Finish signup, confirm the terms/privacy acceptance is stored, then test login and profile access.
5. Complete a checkout using Flutterwave test credentials and verify the resulting payment and access code.
6. Confirm the Flutterwave test webhook points to `https://<render-service>.onrender.com/api/webhooks/flutterwave` and uses the configured test webhook hash.

Do not treat a successful Vercel build or `/health/` response as proof that SMS, payment callbacks, refunds, or consumer/legal requirements are production-ready. Use provider test accounts and keep the demo phone allowlist limited to the people conducting the demo.

## Local CI-equivalent Checks

From the repository root:

```powershell
Push-Location backend
python manage.py makemigrations --check --dry-run
python manage.py test tests
Pop-Location

Push-Location frontend
npm ci
npm run typecheck
npm run build
Pop-Location
```

GitHub Actions runs the backend tests and frontend type/build checks on pushes and pull requests.