#!/usr/bin/env bash
set -euo pipefail
umask 077
export OMNIGENESIS_PRIVATE_BETA=1
python3 platform_admin.py migrate-legacy
python3 platform_admin.py bootstrap
exec python3 omnigenesis_engine.py --serve --port "${PORT:-8080}"
