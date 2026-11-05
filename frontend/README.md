# Netacess frontend (Next.js)

Pages (customer and /admin for staff): landing and plans, sign up, log in, SMS code, checkout (Flutterwave or Espees), payment status with the access code, profile (validity, code, renewal payment method, transaction history, notifications). Admin: dashboard with review queue and provider switches, payments list and detail timeline, audit log.

## Run
    npm install
    cp .env.example .env.local        # BACKEND_URL points at the Django server
    npm run dev                       # http://localhost:3000

Start the backend first (see backend/README.md, `python manage.py runserver`).
The browser only talks to this site; `/api/*` is forwarded to the backend, so no CORS setup is needed.
