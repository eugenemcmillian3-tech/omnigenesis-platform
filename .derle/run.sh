#!/usr/bin/env bash
# ── Derle run script ────────────────────────────────────────────────────────
# Create private local credentials once, then start the authenticated platform.

set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -f .env ]; then
    python3 - <<'PY'
import secrets
from pathlib import Path

values = {
    "OMNIGENESIS_ADMIN_API_KEY": secrets.token_urlsafe(48),
    "OMNIGENESIS_OPERATOR_API_KEY": secrets.token_urlsafe(48),
    "OMNIGENESIS_READONLY_API_KEY": secrets.token_urlsafe(48),
    "OMNIGENESIS_JWT_SECRET": secrets.token_urlsafe(48),
}
Path(".env").write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
Path(".env").chmod(0o600)
PY
fi

set -a
. ./.env
set +a
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
export OMNIGENESIS_PRIVATE_BETA=1
.venv/bin/python platform_admin.py migrate-legacy
.venv/bin/python platform_admin.py bootstrap
printf 'Open http://localhost:8080/ and sign in. Change the bootstrap password with platform_admin.py set-password admin.\n'
exec .venv/bin/python omnigenesis_engine.py --serve --port 8080
