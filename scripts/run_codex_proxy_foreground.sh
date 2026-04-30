#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export HOME="/Users/mehdichaouachi"
cd /Users/mehdichaouachi/.openclaw/projects/codex-proxy

# Keep startup deterministic for launchd. Build only when dist is missing.
if [ ! -f dist/server/standalone.js ]; then
  npm run build
fi

exec env \
  CODEX_PROXY_RUNTIME="${CODEX_PROXY_RUNTIME:-pool}" \
  CODEX_PROXY_INIT_POOL="${CODEX_PROXY_INIT_POOL:-1}" \
  CODEX_PROXY_PREWARM_MODELS="${CODEX_PROXY_PREWARM_MODELS:-gpt-5.4-mini}" \
  node dist/server/standalone.js 3466
