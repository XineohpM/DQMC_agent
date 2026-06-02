#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
START="$ROOT/scripts/start-slackbot-backend"
STOP="$ROOT/scripts/stop-slackbot-backend"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  if [[ "$haystack" != *"$needle"* ]]; then
    fail "expected output to contain: $needle"
  fi
}

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

PROJECT="$TMPDIR/project"
ENV_FILE="$TMPDIR/openacp-env"
OPENACP_LOG="$TMPDIR/openacp-call.log"
FAKE_OPENACP="$PROJECT/.openacp/plugins/node_modules/.bin/openacp"
FAKE_PYTHON="$PROJECT/.venv/bin/python"
mkdir -p "$(dirname "$FAKE_OPENACP")"
mkdir -p "$(dirname "$FAKE_PYTHON")"

cat > "$FAKE_OPENACP" <<'FAKE_OPENACP'
#!/usr/bin/env bash
set -euo pipefail
{
  printf 'cwd=%s\n' "$(pwd)"
  printf 'args=%s\n' "$*"
  printf 'instance=%s\n' "${OPENACP_INSTANCE_ROOT:-}"
  printf 'port=%s\n' "${OPENACP_API_PORT:-}"
  printf 'mode=%s\n' "${OPENACP_RUN_MODE:-}"
  printf 'bot_token=%s\n' "${OPENACP_SLACK_BOT_TOKEN:+set}"
} >> "$OPENACP_TEST_LOG"

case "${1:-}" in
  start)
    printf '{"success":true,"data":{"pid":12345}}\n'
    ;;
  stop)
    printf '{"success":true,"data":{"stopped":true,"pid":12345}}\n'
    ;;
  *)
    printf '{"success":false,"error":{"message":"unexpected command"}}\n'
    exit 1
    ;;
esac
FAKE_OPENACP
chmod +x "$FAKE_OPENACP"

cat > "$FAKE_PYTHON" <<'FAKE_PYTHON'
#!/usr/bin/env bash
set -euo pipefail
printf 'python_args=%s\n' "$*" >> "$OPENACP_TEST_LOG"
case "$*" in
  "-m dqmc_tools.sherlock_auth preflight --timeout-seconds 8")
    exit 1
    ;;
  *)
    printf 'unexpected python command: %s\n' "$*" >&2
    exit 2
    ;;
esac
FAKE_PYTHON
chmod +x "$FAKE_PYTHON"

cat > "$ENV_FILE" <<'ENV'
OPENACP_SLACK_BOT_TOKEN=xoxb-test
OPENACP_SLACK_APP_TOKEN=xapp-test
OPENACP_SLACK_SIGNING_SECRET=test-secret
OPENACP_SLACK_ALLOWED_USER_ID=U123
ENV

start_output="$(
  cd "$TMPDIR"
  DQMC_AGENT_ROOT="$PROJECT" \
    OPENACP_ENV_FILE="$ENV_FILE" \
    OPENACP_API_PORT=29998 \
    OPENACP_TEST_LOG="$OPENACP_LOG" \
    "$START"
)"
assert_contains "$start_output" '"success":true'

call_log="$(cat "$OPENACP_LOG")"
assert_contains "$call_log" "python_args=-m dqmc_tools.sherlock_auth preflight --timeout-seconds 8"
assert_contains "$call_log" "cwd=$PROJECT"
assert_contains "$call_log" "args=start --json --local"
assert_contains "$call_log" "instance=$PROJECT/.openacp"
assert_contains "$call_log" "port=29998"
assert_contains "$call_log" "mode=daemon"
assert_contains "$call_log" "bot_token=set"

stop_output="$(
  cd "$TMPDIR"
  DQMC_AGENT_ROOT="$PROJECT" \
    OPENACP_ENV_FILE="$ENV_FILE" \
    OPENACP_API_PORT=29998 \
    "$STOP"
)"
assert_contains "$stop_output" "No slackbot backend is currently running. Start one with start-slackbot-backend before using this command to stop it."
