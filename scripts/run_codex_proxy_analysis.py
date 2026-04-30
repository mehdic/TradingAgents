#!/usr/bin/env python3
"""Run a safe TradingAgents analysis through the local Codex Proxy.

Research-only harness: no broker integration, no order execution.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph


def check_proxy(base_url: str) -> None:
    health_url = base_url.rstrip("/v1").rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(health_url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - command-line diagnostic
        raise SystemExit(
            f"Codex Proxy is not reachable at {health_url}: {exc}\n"
            "Start it with: (cd /Users/mehdichaouachi/.openclaw/projects/codex-proxy && "
            "nohup env CODEX_PROXY_RUNTIME=pool CODEX_PROXY_INIT_POOL=1 "
            "CODEX_PROXY_PREWARM_MODELS=gpt-5.4-mini node dist/server/standalone.js 3466 "
            "> /tmp/codex-proxy-tradingagents.log 2>&1 &)"
        ) from exc
    if payload.get("status") != "ok":
        raise SystemExit(f"Codex Proxy health check was not ok: {payload}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TradingAgents through Codex Proxy safely.")
    parser.add_argument("ticker", help="Ticker symbol, e.g. NVDA or AAPL")
    parser.add_argument("date", help="Analysis date, YYYY-MM-DD")
    parser.add_argument("--model", default="gpt-5.4-mini", help="Codex Proxy model id")
    parser.add_argument("--base-url", default="http://127.0.0.1:3466/v1", help="Codex Proxy OpenAI-compatible base URL")
    parser.add_argument(
        "--analysts",
        default="market",
        help="Comma-separated analysts. Recommended first test: market. Options include market,social,news,fundamentals",
    )
    parser.add_argument("--debate-rounds", type=int, default=1)
    parser.add_argument("--risk-rounds", type=int, default=1)
    parser.add_argument("--no-checkpoint", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    check_proxy(args.base_url)

    os.environ.setdefault("OPENAI_API_KEY", "codex-proxy-noop")

    analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]
    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "llm_provider": "openai",
            "backend_url": args.base_url,
            "deep_think_llm": args.model,
            "quick_think_llm": args.model,
            "max_debate_rounds": args.debate_rounds,
            "max_risk_discuss_rounds": args.risk_rounds,
            "checkpoint_enabled": not args.no_checkpoint,
        }
    )

    print(f"Running TradingAgents via Codex Proxy: ticker={args.ticker} date={args.date} model={args.model} analysts={analysts}")
    ta = TradingAgentsGraph(selected_analysts=analysts, debug=False, config=config)
    state, decision = ta.propagate(args.ticker, args.date)

    log_path = (
        Path(config["results_dir"])
        / args.ticker
        / "TradingAgentsStrategy_logs"
        / f"full_states_log_{args.date}.json"
    )

    print("\n=== PARSED DECISION ===")
    print(decision)
    print("\n=== FINAL TRADE DECISION ===")
    print(state.get("final_trade_decision", ""))
    print(f"\nFull state log: {log_path}")
    print("\nResearch-only: no broker credentials, no real-money order execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
