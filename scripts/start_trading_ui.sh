#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/mehdichaouachi/.openclaw/workspace-reaper/projects/TradingAgents"
cd "$ROOT"

./scripts/start_codex_proxy_for_tradingagents.sh >/tmp/tradingagents-codex-proxy-start.log 2>&1 || {
  cat /tmp/tradingagents-codex-proxy-start.log >&2
  exit 1
}

PORT="${TRADING_UI_PORT:-8505}"
HOST="${TRADING_UI_HOST:-0.0.0.0}"
LOG="${TRADING_UI_LOG:-/tmp/tradingagents-ui.log}"
PIDFILE="${TRADING_UI_PIDFILE:-/tmp/tradingagents-ui.pid}"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "TradingAgents UI already healthy at http://127.0.0.1:${PORT}"
  exit 0
fi

nohup "$PY" "$ROOT/scripts/trading_ui.py" --host "$HOST" --port "$PORT" > "$LOG" 2>&1 &
echo $! > "$PIDFILE"
sleep 1
curl -fsS "http://127.0.0.1:${PORT}/health"
echo
echo "TradingAgents UI PID: $(cat "$PIDFILE")"
echo "Log: $LOG"

"$ROOT/scripts/start_trading_ui_tunnel.sh"
