#!/usr/bin/env bash
set -euo pipefail
AWS_HOST="ubuntu@100.51.236.128"
SSH_KEY="/Users/mehdichaouachi/.ssh/aws_migration"
REMOTE_PORT="${TRADING_UI_REMOTE_PORT:-18505}"
LOCAL_PORT="${TRADING_UI_PORT:-8505}"
PIDFILE="${TRADING_UI_TUNNEL_PIDFILE:-/tmp/tradingagents-ui-tunnel.pid}"
LOG="${TRADING_UI_TUNNEL_LOG:-/tmp/tradingagents-ui-tunnel.log}"

if ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=8 "$AWS_HOST" "curl -fsS --max-time 5 http://127.0.0.1:${REMOTE_PORT}/health >/dev/null"; then
  echo "TradingAgents reverse tunnel already healthy at AWS 127.0.0.1:${REMOTE_PORT}"
  exit 0
fi

if [ -f "$PIDFILE" ]; then
  kill "$(cat "$PIDFILE")" >/dev/null 2>&1 || true
fi

nohup ssh -i "$SSH_KEY" \
  -o BatchMode=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -N -R "127.0.0.1:${REMOTE_PORT}:127.0.0.1:${LOCAL_PORT}" \
  "$AWS_HOST" > "$LOG" 2>&1 &
echo $! > "$PIDFILE"
sleep 2
ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout=8 "$AWS_HOST" "curl -fsS http://127.0.0.1:${REMOTE_PORT}/health"
echo
echo "TradingAgents reverse tunnel PID: $(cat "$PIDFILE")"
echo "Log: $LOG"
