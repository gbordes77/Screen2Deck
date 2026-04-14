#!/usr/bin/env bash
# Screen2Deck end-to-end smoke test.
#
# Boots the full stack with `make up`, waits for the backend to become
# healthy, uploads a real MTG screenshot from `validation_set/images/`,
# polls the OCR job until it completes, verifies the result is
# structurally sane (non-empty mainboard, Scryfall resolution), and
# exercises the MTGA export endpoint as a final check.
#
# Exits 0 if every step succeeds, non-zero otherwise. The stack is left
# running on success so you can poke at it; use --tear-down to force
# `make down` on exit.
#
# Usage:
#   tests/smoke_test.sh                           # run with default image
#   tests/smoke_test.sh --image path/to/deck.jpg  # custom image
#   tests/smoke_test.sh --tear-down               # always `make down` at the end
#   tests/smoke_test.sh --keep-logs               # dump backend logs even on success
#   tests/smoke_test.sh --no-boot                 # assume the stack is already up
#
# Prerequisites:
#   - Docker + Docker Compose installed and running
#   - .env at the repo root with POSTGRES_PASSWORD, JWT_SECRET_KEY, GEMINI_API_KEY
#   - jq + curl on PATH

set -euo pipefail

# ---------- configuration ----------
BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
FRONT_URL="${FRONT_URL:-http://localhost:3000}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"   # seconds to wait for /health
JOB_TIMEOUT="${JOB_TIMEOUT:-120}"         # seconds to wait for an OCR job
MIN_MAIN_CARDS="${MIN_MAIN_CARDS:-20}"    # minimum total qty in mainboard
MIN_RESOLUTION_RATE="${MIN_RESOLUTION_RATE:-50}"  # % of cards that must have scryfall_id

# ---------- cli parsing ----------
TEST_IMAGE=""
TEAR_DOWN=false
KEEP_LOGS=false
NO_BOOT=false

while [ $# -gt 0 ]; do
  case "$1" in
    --image)        TEST_IMAGE="$2"; shift 2 ;;
    --tear-down)    TEAR_DOWN=true;  shift ;;
    --keep-logs)    KEEP_LOGS=true;  shift ;;
    --no-boot)      NO_BOOT=true;    shift ;;
    -h|--help)
      sed -n '2,30p' "$0" | sed 's/^# //; s/^#//'
      exit 0
      ;;
    *)
      echo "unknown flag: $1" >&2
      exit 64
      ;;
  esac
done

# ---------- output helpers ----------
if [ -t 1 ]; then
  c_red=$'\033[31m'; c_green=$'\033[32m'; c_yellow=$'\033[33m'
  c_blue=$'\033[34m'; c_dim=$'\033[2m'; c_reset=$'\033[0m'
else
  c_red=""; c_green=""; c_yellow=""; c_blue=""; c_dim=""; c_reset=""
fi

log()    { printf "%s[%s]%s %s\n" "$c_blue"   "…" "$c_reset" "$*"; }
ok()     { printf "%s[%s]%s %s\n" "$c_green"  "✓" "$c_reset" "$*"; }
warn()   { printf "%s[%s]%s %s\n" "$c_yellow" "!" "$c_reset" "$*"; }
fail()   { printf "%s[%s]%s %s\n" "$c_red"    "✗" "$c_reset" "$*"; }
hr()     { printf "%s%s%s\n" "$c_dim" "────────────────────────────────────────────────────" "$c_reset"; }

# ---------- change to repo root ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ---------- preflight ----------
hr
log "Screen2Deck smoke test — starting from $REPO_ROOT"
hr

# 1) Required binaries
for bin in docker curl jq; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    fail "missing required binary: $bin"
    exit 1
  fi
done
if ! docker compose version >/dev/null 2>&1; then
  fail "docker compose plugin not available (run \`docker compose version\`)"
  exit 1
fi
ok "docker, docker compose, curl, jq all available"

# 2) Required env vars (read from .env if present)
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

MISSING=()
for var in POSTGRES_PASSWORD JWT_SECRET_KEY GEMINI_API_KEY; do
  if [ -z "${!var:-}" ]; then
    MISSING+=("$var")
  fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
  fail "missing required env var(s): ${MISSING[*]}"
  echo
  echo "Set them in .env at the repo root. Quick generation:"
  echo "  POSTGRES_PASSWORD=\$(openssl rand -hex 16)"
  echo "  JWT_SECRET_KEY=\$(openssl rand -base64 32)"
  echo "  GEMINI_API_KEY=   # paste from https://aistudio.google.com/app/apikey"
  exit 1
fi
ok "env vars POSTGRES_PASSWORD, JWT_SECRET_KEY, GEMINI_API_KEY are set"

# 3) Scryfall bulk hydrate (warning only — test can still run without it)
BULK_PATH="${SCRYFALL_BULK_PATH:-backend/app/data/scryfall-default-cards.json}"
if [ ! -f "$BULK_PATH" ]; then
  warn "Scryfall bulk file not found at $BULK_PATH"
  warn "first run will hit the online /cards/collection endpoint — slower and subject to rate limit"
  warn "to pre-hydrate: python backend/scripts/download_scryfall.py"
else
  SIZE_MB=$(( $(stat -f%z "$BULK_PATH" 2>/dev/null || stat -c%s "$BULK_PATH" 2>/dev/null || echo 0) / 1024 / 1024 ))
  ok "Scryfall bulk file present (${SIZE_MB} MB)"
fi

# 4) Test image
if [ -z "$TEST_IMAGE" ]; then
  CANDIDATES=(
    "validation_set/images/MTGA deck list_1535x728.jpeg"
    "validation_set/images/MTGA deck list 4_1920x1080.jpeg"
    "validation_set/images/MTGO deck list usual_1763x791.jpeg"
  )
  for c in "${CANDIDATES[@]}"; do
    if [ -f "$c" ]; then
      TEST_IMAGE="$c"
      break
    fi
  done
  if [ -z "$TEST_IMAGE" ]; then
    TEST_IMAGE="$(find validation_set/images tests/validation-images -type f \
      \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) \
      2>/dev/null | head -n 1)"
  fi
fi
if [ -z "$TEST_IMAGE" ] || [ ! -f "$TEST_IMAGE" ]; then
  fail "no test image found (tried validation_set/images/*, tests/validation-images/*)"
  echo "Pass one explicitly: $0 --image path/to/deck.jpg"
  exit 1
fi
IMAGE_SIZE=$(stat -f%z "$TEST_IMAGE" 2>/dev/null || stat -c%s "$TEST_IMAGE" 2>/dev/null || echo 0)
ok "test image: $TEST_IMAGE ($((IMAGE_SIZE / 1024)) KB)"

hr

# ---------- boot ----------
cleanup() {
  local ec=$?
  if [ "$KEEP_LOGS" = "true" ] || { [ $ec -ne 0 ] && [ "$NO_BOOT" = "false" ]; }; then
    echo
    hr
    log "backend logs (last 80 lines)"
    hr
    docker compose logs backend --tail 80 2>&1 || true
  fi
  if [ "$TEAR_DOWN" = "true" ]; then
    echo
    log "tearing stack down (make down)..."
    make down >/dev/null 2>&1 || true
  fi
  exit $ec
}
trap cleanup EXIT

if [ "$NO_BOOT" = "false" ]; then
  log "starting stack with 'make up'..."
  if ! make up >/dev/null 2>&1; then
    fail "make up returned non-zero"
    exit 1
  fi
  ok "make up completed"
else
  warn "skipping boot (--no-boot)"
fi

# ---------- wait for backend ----------
log "waiting for backend health at $BACKEND_URL/health (timeout ${HEALTH_TIMEOUT}s)..."
ELAPSED=0
while (( ELAPSED < HEALTH_TIMEOUT )); do
  if curl -fsS "$BACKEND_URL/health" >/dev/null 2>&1; then
    ok "backend healthy after ${ELAPSED}s"
    break
  fi
  sleep 3
  ELAPSED=$((ELAPSED + 3))
done
if (( ELAPSED >= HEALTH_TIMEOUT )); then
  fail "backend never became healthy"
  exit 1
fi

# ---------- upload ----------
hr
log "POST $BACKEND_URL/api/ocr/upload with $TEST_IMAGE"
UPLOAD_RESP="$(curl -fsS -X POST "$BACKEND_URL/api/ocr/upload" \
  -F "file=@${TEST_IMAGE}")" || {
  fail "upload failed"
  exit 1
}
JOB_ID="$(echo "$UPLOAD_RESP" | jq -r '.jobId // empty')"
if [ -z "$JOB_ID" ]; then
  fail "upload response had no jobId: $UPLOAD_RESP"
  exit 1
fi
CACHED="$(echo "$UPLOAD_RESP" | jq -r '.cached // false')"
ok "got jobId=$JOB_ID (cached=$CACHED)"

# ---------- poll status ----------
log "polling GET $BACKEND_URL/api/ocr/status/$JOB_ID (timeout ${JOB_TIMEOUT}s)..."
ELAPSED=0
STATUS_RESP=""
INTERVAL=1
while (( ELAPSED < JOB_TIMEOUT )); do
  STATUS_RESP="$(curl -fsS "$BACKEND_URL/api/ocr/status/$JOB_ID")" || {
    fail "status request failed"
    exit 1
  }
  STATE="$(echo "$STATUS_RESP" | jq -r '.state')"
  PROGRESS="$(echo "$STATUS_RESP" | jq -r '.progress // 0')"
  case "$STATE" in
    completed)
      ok "job completed in ${ELAPSED}s (final progress=${PROGRESS})"
      break
      ;;
    failed)
      fail "job failed: $(echo "$STATUS_RESP" | jq -r '.error // "no error message"')"
      echo "$STATUS_RESP" | jq '.'
      exit 1
      ;;
    queued|processing)
      printf "    state=%s progress=%s elapsed=%ss\r" "$STATE" "$PROGRESS" "$ELAPSED"
      sleep "$INTERVAL"
      ELAPSED=$((ELAPSED + INTERVAL))
      if (( INTERVAL < 3 )); then INTERVAL=$((INTERVAL + 1)); fi
      ;;
    *)
      fail "unexpected job state: $STATE"
      echo "$STATUS_RESP" | jq '.'
      exit 1
      ;;
  esac
done
echo
if [ "$STATE" != "completed" ]; then
  fail "job did not complete within ${JOB_TIMEOUT}s (last state=$STATE)"
  exit 1
fi

# ---------- verify result ----------
hr
log "verifying deck structure..."

MAIN_QTY="$(echo "$STATUS_RESP" | jq '([.result.normalized.main[]?.qty] | add) // 0')"
SIDE_QTY="$(echo "$STATUS_RESP" | jq '([.result.normalized.side[]?.qty] | add) // 0')"
MAIN_COUNT="$(echo "$STATUS_RESP" | jq '.result.normalized.main | length')"
SIDE_COUNT="$(echo "$STATUS_RESP" | jq '.result.normalized.side | length')"
RESOLVED_COUNT="$(echo "$STATUS_RESP" \
  | jq '[.result.normalized.main[]? | select(.scryfall_id != null)] | length')"

ok "deck shape: main=${MAIN_QTY} (${MAIN_COUNT} distinct) / side=${SIDE_QTY} (${SIDE_COUNT} distinct)"
ok "scryfall resolution: ${RESOLVED_COUNT}/${MAIN_COUNT} mainboard cards matched"

if (( MAIN_QTY < MIN_MAIN_CARDS )); then
  fail "mainboard has only ${MAIN_QTY} cards, expected at least ${MIN_MAIN_CARDS}"
  echo "$STATUS_RESP" | jq '.result.normalized'
  exit 1
fi

if (( MAIN_COUNT > 0 )); then
  RATE=$(( RESOLVED_COUNT * 100 / MAIN_COUNT ))
  if (( RATE < MIN_RESOLUTION_RATE )); then
    fail "Scryfall resolution rate ${RATE}% < ${MIN_RESOLUTION_RATE}% — either Scryfall is down or OCR output is garbage"
    echo "$STATUS_RESP" | jq '.result.normalized.main[0:5]'
    exit 1
  fi
  ok "resolution rate ${RATE}% >= ${MIN_RESOLUTION_RATE}%"
fi

# sample of what came out
echo
hr
log "first 5 main deck cards (sanity check):"
echo "$STATUS_RESP" | jq -r '.result.normalized.main[0:5] | .[] | "   \(.qty)× \(.name)  [\(.scryfall_id // "unresolved")]"'
hr

# ---------- test export endpoint ----------
log "POST $BACKEND_URL/api/export/mtga with the normalized deck..."
EXPORT_PAYLOAD="$(echo "$STATUS_RESP" | jq '.result.normalized')"
EXPORT_RESP="$(curl -fsS -X POST "$BACKEND_URL/api/export/mtga" \
  -H "Content-Type: application/json" \
  -d "$EXPORT_PAYLOAD")" || {
  fail "export request failed"
  exit 1
}
EXPORT_LINES="$(echo "$EXPORT_RESP" | wc -l | tr -d ' ')"
if (( EXPORT_LINES < 5 )); then
  fail "MTGA export only produced ${EXPORT_LINES} lines — looks broken"
  echo "$EXPORT_RESP"
  exit 1
fi
ok "MTGA export returned ${EXPORT_LINES} lines"

# ---------- done ----------
echo
hr
ok "ALL CHECKS PASSED"
hr
echo
echo "Stack is running at:"
echo "  Backend:  $BACKEND_URL"
echo "  Webapp:   $FRONT_URL"
echo "  Logs:     make logs"
echo
echo "Tear down when you're done:"
echo "  make down"
echo
exit 0
