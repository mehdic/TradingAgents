#!/usr/bin/env bash
set -euo pipefail
cd /Users/mehdichaouachi/.openclaw/projects/codex-proxy
npm run build >/tmp/codex-proxy-build.log 2>&1
if curl -fsS http://127.0.0.1:3466/health >/dev/null 2>&1; then
  echo "Codex Proxy already healthy at http://127.0.0.1:3466"
  exit 0
fi
nohup env CODEX_PROXY_RUNTIME=pool CODEX_PROXY_INIT_POOL=1 CODEX_PROXY_PREWARM_MODELS=gpt-5.4-mini \
  node dist/server/standalone.js 3466 > /tmp/codex-proxy-tradingagents.log 2>&1 &
echo $! > /tmp/codex-proxy-tradingagents.pid
sleep 2
curl -fsS http://127.0.0.1:3466/health
echo
echo "Codex Proxy PID: $(cat /tmp/codex-proxy-tradingagents.pid)"
echo "Log: /tmp/codex-proxy-tradingagents.log"
