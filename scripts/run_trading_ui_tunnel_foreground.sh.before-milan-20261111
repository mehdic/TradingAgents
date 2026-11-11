#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export HOME="/Users/mehdichaouachi"
AWS_HOST="ubuntu@100.51.236.128"
SSH_KEY="/Users/mehdichaouachi/.ssh/aws_migration"
REMOTE_PORT="${TRADING_UI_REMOTE_PORT:-18505}"
LOCAL_PORT="${TRADING_UI_PORT:-8505}"

exec ssh -i "$SSH_KEY" \
  -o BatchMode=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -N -R "127.0.0.1:${REMOTE_PORT}:127.0.0.1:${LOCAL_PORT}" \
  "$AWS_HOST"
