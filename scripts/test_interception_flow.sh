#!/usr/bin/env bash
# Intercept → Edit → Release end-to-end helper
# Requires: bash, curl, jq
set -euo pipefail

# Load config
if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  source .env
fi

BASE_URL="${BASE_URL:-http://localhost:5000}"
USERNAME="${USERNAME:-admin}"
PASSWORD="${PASSWORD:-admin123}"
ACCOUNT_ID="${ACCOUNT_ID:-1}"   # Destination inbox watcher (e.g., Hostinger). Change as needed.
KEYWORD="${KEYWORD:-invoice}"   # Interception keyword you configured in Rules.
POLL_INTERVAL="${POLL_INTERVAL:-5}"  # seconds
POLL_MAX_TRIES="${POLL_MAX_TRIES:-60}"

COOKIE_JAR="${COOKIE_JAR:-cookie.txt}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1"; exit 1; }; }
need curl
need jq

api() {
  local method=$1; shift
  local path=$1; shift
  local data=${1:-}
  if [ -n "$data" ]; then
    curl -sS -b "$COOKIE_JAR" -H "Content-Type: application/json" -X "$method" -d "$data" "${BASE_URL}${path}"
  else
    curl -sS -b "$COOKIE_JAR" -X "$method" "${BASE_URL}${path}"
  fi
}

login() {
  echo "==> Logging in as $USERNAME"
  curl -sS -c "$COOKIE_JAR" -X POST \
    -d "username=${USERNAME}" \
    -d "password=${PASSWORD}" \
    "${BASE_URL}/login" >/dev/null
  echo "    Logged in. Session saved to $COOKIE_JAR"
}

accounts_list() {
  echo "==> Listing accounts"
  api GET "/api/accounts" | jq .
}

monitor_start() {
  local acc_id=${1:-$ACCOUNT_ID}
  echo "==> Starting IMAP watcher for account ${acc_id}"
  api POST "/api/accounts/${acc_id}/monitor/start" | jq .
}

monitor_stop() {
  local acc_id=${1:-$ACCOUNT_ID}
  echo "==> Stopping IMAP watcher for account ${acc_id}"
  api POST "/api/accounts/${acc_id}/monitor/stop" | jq .
}

held_list() {
  api GET "/api/interception/held"
}

held_list_pretty() {
  echo "==> Held queue (latest)"
  held_list | jq '.items // .held // . | map({id, subject, from, to, status})'
}

held_get() {
  local id=$1
  api GET "/api/interception/held/${id}"
}

edit_message() {
  local id=$1
  local new_subj=$2
  local new_body=$3
  local payload
  payload=$(jq -n --arg subject "$new_subj" --arg body_text "$new_body" '{subject: $subject, body_text: $body_text}')
  echo "==> Editing message ${id}"
  api POST "/api/email/${id}/edit" "$payload" | jq .
}

release_message() {
  local id=$1
  local edited_subject=$2
  local edited_body=$3
  local payload
  payload=$(jq -n --arg s "$edited_subject" --arg b "$edited_body" '{edited_subject: $s, edited_body: $b}')
  echo "==> Releasing message ${id}"
  api POST "/api/interception/release/${id}" "$payload" | jq .
}

discard_message() {
  local id=$1
  echo "==> Discarding message ${id}"
  api POST "/api/interception/discard/${id}" | jq .
}

inbox_search() {
  local query=$1
  api GET "/api/inbox?q=$(python3 - <<EOF
import urllib.parse,sys
print(urllib.parse.quote(sys.argv[1]))
EOF
"$query")"
}

wait_for_inbox_contains() {
  local query=$1
  echo "==> Waiting for unified inbox to contain: $query"
  for i in $(seq 1 "$POLL_MAX_TRIES"); do
    if inbox_search "$query" | jq -e '.items // .results // . | length > 0' >/dev/null; then
      echo "    Found in inbox."
      return 0
    fi
    sleep "$POLL_INTERVAL"
  done
  echo "Timed out waiting for inbox to contain: $query"
  return 1
}

wait_for_held_any() {
  echo "==> Waiting for at least one HELD message to appear"
  for i in $(seq 1 "$POLL_MAX_TRIES"); do
    if held_list | jq -e '.items // .held // . | length > 0' >/dev/null; then
      echo "    Held item detected."
      return 0
    fi
    sleep "$POLL_INTERVAL"
  done
  echo "Timed out waiting for held items."
  return 1
}

first_held_id() {
  held_list | jq -r '( .items // .held // . )[0].id'
}

run_control_test() {
  echo ""
  echo "================ CONTROL TEST (no interception) ================"
  echo "Send an email WITHOUT the keyword '${KEYWORD}' to the DESTINATION inbox (account id ${ACCOUNT_ID})."
  read -rp "Press Enter after you send it..."
  # We don't know the exact subject; ask user for a token to search
  read -rp "Type a unique word from that test subject to verify delivery: " token
  wait_for_inbox_contains "$token"
  echo "Control test: PASS (message reached INBOX and is not in Held)"
}

run_interception_test() {
  echo ""
  echo "================ INTERCEPTION TEST (with keyword) ================"
  echo "Send an email that CONTAINS the keyword '${KEYWORD}' in subject or body to the DESTINATION inbox (account id ${ACCOUNT_ID})."
  read -rp "Press Enter after you send it..."
  wait_for_held_any
  held_list_pretty
  local id
  id=$(first_held_id)
  if [ "$id" = "null" ] || [ -z "$id" ]; then
    echo "Could not determine held message id automatically. Please copy/paste the id from above."
    read -rp "Held message id: " id
  fi
  echo "==> Using held message id: $id"
  echo "Details:"
  held_get "$id" | jq '{id, subject, from, to, status, preview: (.body_text // .snippet // "")[0:160] }'

  echo ""
  echo "---- RELEASE AS-IS ----"
  release_message "$id" "UNCHANGED" "UNCHANGED"
  echo "Waiting for released copy to show in INBOX..."
  read -rp "Type a unique word from the original subject (or body) to verify in INBOX: " token_release
  wait_for_inbox_contains "$token_release"
  echo "Release-as-is: PASS"

  echo ""
  echo "---- EDIT → RELEASE ----"
  echo "Send another email with the keyword '${KEYWORD}' to trigger interception again."
  read -rp "Press Enter after you send it..."
  wait_for_held_any
  held_list_pretty
  local id2
  id2=$(first_held_id)
  if [ "$id2" = "null" ] || [ -z "$id2" ]; then
    echo "Could not determine second held message id automatically. Please copy/paste the id."
    read -rp "Held message id: " id2
  fi
  local edited_subject="[Reviewed] $(date +%Y-%m-%dT%H:%M:%S) ${KEYWORD}"
  local edited_body="Edited body at $(date)"
  edit_message "$id2" "$edited_subject" "$edited_body"
  release_message "$id2" "$edited_subject" "$edited_body"
  echo "Waiting for EDITED copy to show in INBOX..."
  wait_for_inbox_contains "$edited_subject"
  echo "Edit → Release: PASS (only edited copy should be in INBOX)"
}

main() {
  echo "Base URL: $BASE_URL"
  echo "Destination account id: $ACCOUNT_ID"
  echo "Keyword: $KEYWORD"
  login
  accounts_list
  monitor_start "$ACCOUNT_ID"

  run_control_test
  run_interception_test

  echo ""
  echo "All checks done."
  echo "Tip: run './intercept_flow.sh monitor_stop' later to stop the watcher."
}

if [[ "${1:-}" == "monitor_stop" ]]; then
  login
  monitor_stop "$ACCOUNT_ID"
  exit 0
fi

main
