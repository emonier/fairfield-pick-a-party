# Deployment Guide

This guide targets a self-hosted macOS desktop and covers installation, service configuration, HTTPS, and Square production setup.

## 1. System Preparation

1. Install the latest Python 3 (>=3.11). Homebrew works well:
   ```bash
   brew install python@3.11
   ```
2. Install a process supervisor and reverse proxy of your choice:
   - **Gunicorn** to run the Flask app: `pip install gunicorn`
   - **Caddy** *(recommended for macOS)* or **Nginx/Apache** for TLS termination.
3. Create a dedicated user account (optional but safer) that will own the app files and run the service.

## 2. Application Setup

```bash
git clone <repo-url> pick-a-party
cd pick-a-party
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp docs/env.example .env
nano .env  # fill in production Square keys, shared password, etc.

mkdir -p instance
flask --app manage.py db upgrade
flask --app manage.py create-admin you@school.org
```

Keep the `instance/school_fundraising.db` file backed up (Time Machine or rsync to an external disk).

## 3. Running Under Gunicorn

Create `scripts/start.sh` (executable) containing:
```bash
#!/usr/bin/env bash
source /path/to/pick-a-party/.venv/bin/activate
cd /path/to/pick-a-party
exec gunicorn --bind 127.0.0.1:8000 --workers 3 "manage:app"
```

### Launchd service (macOS)
Create `~/Library/LaunchAgents/com.school.pickaparty.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.school.pickaparty</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>/path/to/pick-a-party/scripts/start.sh</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/tmp/pickaparty.out</string>
    <key>StandardErrorPath</key><string>/tmp/pickaparty.err</string>
    <key>EnvironmentVariables</key>
    <dict>
      <key>FLASK_ENV</key><string>production</string>
    </dict>
  </dict>
</plist>
```

Load it with `launchctl load ~/Library/LaunchAgents/com.school.pickaparty.plist`.

## 4. Reverse Proxy & HTTPS

### Option A: Caddy (automatic HTTPS)

1. Install: `brew install caddy`
2. Configure `/usr/local/etc/Caddyfile`:
   ```
   party.yourdomain.com {
     reverse_proxy 127.0.0.1:8000
     encode gzip
   }
   ```
3. Run `sudo caddy start`. Caddy obtains and renews Let’s Encrypt certificates automatically.

### Option B: Apache (mod_proxy)

```
LoadModule proxy_module libexec/apache2/mod_proxy.so
LoadModule proxy_http_module libexec/apache2/mod_proxy_http.so

<VirtualHost *:80>
    ServerName party.yourdomain.com
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

Combine with `certbot` or `acme.sh` for HTTPS on port 443.

### No Domain Yet?

- Use a free dynamic DNS (DuckDNS) to map your home IP.
- Alternatively, run behind a Cloudflare Tunnel to avoid opening ports on your router. Cloudflare provides a free hostname with automatic HTTPS.

## 5. Square Production Checklist

1. Switch `.env` to production credentials and set `SQUARE_ENVIRONMENT=production`.
2. Update the Square Web Payments domain whitelist to your public hostname.
3. In Square dashboard → Webhooks, point to `https://party.yourdomain.com/webhooks/square` and paste the production signature key.
4. Test with a $1 real charge before announcing broadly.
5. Monitor `tmp/pickaparty.out`/`.err` or configure structured logging to a file.

## 6. Backups & Maintenance

- **Database**: schedule a nightly copy of `instance/school_fundraising.db` to an external drive (`launchd` + `rsync`).
- **Logs**: rotate `tmp/pickaparty.*` monthly.
- **Updates**:
  ```bash
  source .venv/bin/activate
  git pull
  pip install -r requirements.txt
  flask --app manage.py db upgrade
  launchctl unload/load com.school.pickaparty.plist
  ```

## 7. Security Reminders

- Use a long random `SECRET_KEY` and shared family password; change both annually.
- Limit admin accounts to school staff; disable default account when people leave.
- Keep macOS, Python, and dependencies patched.
- Restrict router port forwarding to HTTP/HTTPS only and monitor for suspicious traffic.

