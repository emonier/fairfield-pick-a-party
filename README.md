# Pick-a-Party Fundraising Portal

Flask web app that lets Fairfield Elementary families browse school-hosted parties, add tickets to a cart, pay online through Square, and gives administrators tools to manage events, registrations, and payments.

## Features
- Family-facing catalog with remaining spots, pricing, shared-password access, cart, and Square Web Payments checkout.
- Checkout success page that summarizes purchases and surfaces host contact info.
- Admin console for CRUD party management, CSV import/export of registrations, dashboards, and payment tracking.
- Square SDK integration with payment capture and webhook reconciliation.
- SQLite persistence via SQLAlchemy with Flask-Migrate for schema management.

## Quick Start (Local Development)
1. **Create and activate a virtualenv**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Bootstrap environment variables**
   Copy `docs/env.example` to `.env` and fill in the Square sandbox keys plus a strong `SECRET_KEY` and `SECURITY_SHARED_PASSWORD`.

4. **Initialize the database**
   ```bash
   flask --app manage.py db init  # first time only
   flask --app manage.py db migrate
   flask --app manage.py db upgrade
   flask --app manage.py create-admin you@school.org
   ```

5. **Run the server**
   ```bash
   flask --app manage.py --debug run
   ```

The family portal is served at `http://127.0.0.1:5000/`; admin tools live under `/admin`.

## Square Configuration
- Create a Square sandbox application and copy the **Application ID**, **Access Token**, and **Location ID** into your `.env`.
- On the Square developer dashboard set the Web Payments redirect URL to your checkout page.
- Register the webhook endpoint `https://<your-host>/webhooks/square` with the signature key copied to `SQUARE_WEBHOOK_SIGNATURE_KEY`.
- When ready for production, swap sandbox keys with production values and update `SQUARE_ENVIRONMENT=production`.

## Deployment Notes
- See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for detailed hosting, HTTPS, and service supervision guidance.
- Recommended production entrypoint:
  ```bash
  gunicorn --bind 0.0.0.0:8000 "manage:app"
  ```
- Be sure to keep the `instance` directory writable so SQLite can create `school_fundraising.db`.

## Admin Workflow
- Add or edit parties via `/admin/parties`.
- Upload historical sign-ups with CSV import (columns: `family_name,family_email,family_phone,quantity,status,amount_cents`).
- Track real-time payments on the dashboard and in `Registrations`.

## Additional Resources
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) – macOS hosting, Apache/Nginx reverse proxy, HTTPS, backups.
- Square Web Payments documentation: <https://developer.squareup.com/docs/web-payments/overview>
- Flask documentation: <https://flask.palletsprojects.com/>
