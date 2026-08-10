#!/usr/bin/env bash
# One-time DataHub OSS setup after `datahub docker quickstart`:
#   1. wait for GMS + frontend health
#   2. mint a personal access token (auth is enabled by default in quickstart)
#   3. write DATAHUB_GMS_TOKEN into .env (never committed)
#   4. ingest the demo pipeline metadata + verify a real round-trip
set -euo pipefail
cd "$(dirname "$0")/.."

GMS_URL="${DATAHUB_GMS_URL:-http://localhost:8080}"
FRONTEND_URL="${DATAHUB_FRONTEND_URL:-http://localhost:9002}"
export PATH="$HOME/.local/bin:$PATH"

echo "Waiting for DataHub GMS at $GMS_URL ..."
for i in $(seq 1 120); do
  curl -sf "$GMS_URL/health" >/dev/null 2>&1 && break
  sleep 5
done
curl -sf "$GMS_URL/health" >/dev/null || { echo "GMS not healthy"; exit 1; }
echo "GMS healthy. Waiting for frontend at $FRONTEND_URL ..."
for i in $(seq 1 60); do
  curl -sf "$FRONTEND_URL" >/dev/null 2>&1 && break
  sleep 5
done

echo "Minting personal access token (user: datahub) ..."
datahub init --use-password --username datahub --password datahub --token-duration ONE_MONTH 2>/dev/null \
  || datahub init --username datahub --password datahub --token-duration ONE_MONTH

TOKEN=$(python3 - <<'PY'
import pathlib, yaml
cfg = yaml.safe_load(pathlib.Path.home().joinpath(".datahubenv").read_text())
print(cfg["gms"]["token"])
PY
)
[ -n "$TOKEN" ] || { echo "failed to extract token from ~/.datahubenv"; exit 1; }

touch .env
if grep -q '^DATAHUB_GMS_TOKEN=' .env; then
  python3 - "$TOKEN" <<'PY'
import pathlib, re, sys
p = pathlib.Path(".env")
p.write_text(re.sub(r"^DATAHUB_GMS_TOKEN=.*$", f"DATAHUB_GMS_TOKEN={sys.argv[1]}", p.read_text(), flags=re.M))
PY
else
  printf '\nDATAHUB_GMS_TOKEN=%s\n' "$TOKEN" >> .env
fi
grep -q '^DATAHUB_GMS_URL=' .env || printf 'DATAHUB_GMS_URL=%s\n' "$GMS_URL" >> .env
echo "Token written to .env"

echo "Ingesting demo pipeline metadata into DataHub ..."
uv run python -m blackbox.datahub.ingest
echo "DataHub setup complete."
