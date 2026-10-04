#!/bin/bash
# One-time setup for alert emails through a Hostinger mailbox (SMTP).
# Run:  ./scripts/setup_email.sh
# It asks for the mailbox, its password (typed hidden), and where alerts should go, writes them
# to .env (which is not committed to git), restarts the backend, and sends a test email.
set -euo pipefail
cd "$(dirname "$0")/.."

read -rp "Hostinger mailbox address that SENDS the alerts (e.g. alerts@yourdomain.com): " SMTP_USER
read -rsp "Password for that mailbox (typing is hidden): " SMTP_PASSWORD; echo
read -rp "Where should alerts be delivered? [${SMTP_USER}]: " ALERT_EMAIL_TO
ALERT_EMAIL_TO=${ALERT_EMAIL_TO:-$SMTP_USER}

export SMTP_HOST="${SMTP_HOST:-smtp.hostinger.com}" SMTP_PORT="${SMTP_PORT:-465}"
export SMTP_USER SMTP_PASSWORD ALERT_EMAIL_TO SMTP_FROM="$SMTP_USER"

python3 scripts/_set_env.py .env SMTP_HOST SMTP_PORT SMTP_USER SMTP_PASSWORD SMTP_FROM ALERT_EMAIL_TO
chmod 600 .env
echo "Saved to .env. Restarting the backend..."
docker compose up -d --force-recreate backend >/dev/null
for i in $(seq 1 30); do curl -sf localhost:8001/api/health >/dev/null && break; sleep 2; done

echo "Sending a test email to ${ALERT_EMAIL_TO}..."
curl -s -X POST localhost:8001/api/alerts/test-email; echo
echo "If the status says 'emailed to ...', check that inbox. If it says 'email failed', the reason is in the status."
