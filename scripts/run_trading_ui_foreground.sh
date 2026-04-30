#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export HOME="/Users/mehdichaouachi"
ROOT="/Users/mehdichaouachi/.openclaw/workspace-reaper/projects/TradingAgents"
cd "$ROOT"

PORT="${TRADING_UI_PORT:-8505}"
HOST="${TRADING_UI_HOST:-0.0.0.0}"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

exec "$PY" "$ROOT/scripts/trading_ui.py" --host "$HOST" --port "$PORT"
