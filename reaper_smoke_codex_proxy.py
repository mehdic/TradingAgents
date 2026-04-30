import os

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# Codex proxy is OpenAI-compatible and owns Codex auth through the official app-server.
os.environ.setdefault("OPENAI_API_KEY", "codex-proxy-noop")

config = DEFAULT_CONFIG.copy()
config.update({
    "llm_provider": "openai",
    "backend_url": "http://127.0.0.1:3466/v1",
    "deep_think_llm": "gpt-5.4-mini",
    "quick_think_llm": "gpt-5.4-mini",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "checkpoint_enabled": True,
})

# Minimal first live analysis: old date, single ticker, no broker integration.
ta = TradingAgentsGraph(
    selected_analysts=["market"],
    debug=False,
    config=config,
)

state, decision = ta.propagate("NVDA", "2026-01-15")
print("=== DECISION ===")
print(decision)
print("=== FINAL TRADE DECISION ===")
print(state.get("final_trade_decision", ""))
