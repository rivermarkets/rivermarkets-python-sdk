#!/usr/bin/env bash
# Refresh the OpenAPI spec, regenerate the Python SDK, and re-apply
# hand-edits. Idempotent — safe to re-run.
#
# Usage:
#   bash fern/regen.sh                              # use prod openapi
#   OPENAPI_URL=https://staging.../openapi.json \
#       bash fern/regen.sh                          # override source

set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
OPENAPI_URL="${OPENAPI_URL:-https://api.rivermarkets.com/openapi.json}"
FERN_VERSION="${FERN_VERSION:-4.62.3}"

echo "[1/4] fetching OpenAPI spec from $OPENAPI_URL"
curl -fsSL "$OPENAPI_URL" -o "$HERE/openapi.raw.json"

echo "[2/4] filtering spec to documented routes"
python3 "$HERE/filter_spec.py"

echo "[3/4] running fern generate (v$FERN_VERSION)"
cd "$HERE"
# `set -o pipefail` + `yes |` would abort on SIGPIPE; feed a single answer instead.
printf 'Yes\n' | npx --yes "fern-api@$FERN_VERSION" generate --local --group local

echo "[4/4] re-applying hand-edits"
python3 "$HERE/postprocess.py"

cd "$ROOT"
echo "regen complete."
