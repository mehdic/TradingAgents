#!/usr/bin/env python3
"""Web UI for running and archiving TradingAgents analyses via Codex Proxy.

Research-only interface. It never stores broker credentials or places orders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_codex_proxy_analysis.py"
PYTHON = ROOT / ".venv" / "bin" / "python"
TA_HOME = Path.home() / ".tradingagents"
LOGS_DIR = TA_HOME / "logs"
RUNS_DIR = TA_HOME / "ui_runs"
JOBS: dict[str, dict[str, object]] = {}
JOBS_LOCK = threading.Lock()
STALE_JOB_SECONDS = 5 * 60
TICKER_RE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")
ANALYSTS = ["market", "social", "news", "fundamentals"]
MODELS = ["gpt-5.4-mini", "gpt-5.5", "gpt-5.4", "gpt-5.2"]
PORTFOLIO_PATH = Path("/Users/mehdichaouachi/.openclaw/workspace/memory/mehdi-portfolio.md")
DEFAULT_PORTFOLIO_TICKERS = ["NVDA", "AMZN", "AAPL", "MSFT", "GOOGL", "VUSA", "META", "STLA"]

STYLE = """
:root{color-scheme:dark;--bg:#090b10;--card:#111722;--muted:#91a0b7;--text:#edf2ff;--gold:#d9a441;--bad:#ff6b6b;--ok:#46d17d;--line:#243044}*{box-sizing:border-box}body{margin:0;font:16px/1.45 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto;background:radial-gradient(circle at 20% 0%,#172137 0,#090b10 36rem);color:var(--text)}main{max-width:1200px;margin:0 auto;padding:42px 20px 80px}.hero{display:flex;gap:18px;align-items:center;margin-bottom:28px}.sigil{width:54px;height:54px;border:1px solid #6d4d16;border-radius:16px;background:linear-gradient(135deg,#2b1d08,#d9a441);display:grid;place-items:center;font-size:28px;box-shadow:0 0 60px rgba(217,164,65,.2)}h1{margin:0;font-size:clamp(30px,5vw,54px);letter-spacing:-.04em}h2,h3{margin-top:0}.sub{color:var(--muted);margin:.25rem 0 0}.grid{display:grid;grid-template-columns:380px 1fr;gap:20px}.detailgrid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:20px}@media(max-width:900px){main{padding:24px 12px 56px}.grid,.detailgrid{grid-template-columns:1fr}.card{padding:16px;border-radius:18px}.hero{align-items:flex-start}.sigil{width:44px;height:44px;border-radius:14px;font-size:23px}.checks{grid-template-columns:1fr}.table{display:block;overflow-x:auto;white-space:nowrap}.btnrow{display:grid;grid-template-columns:1fr}.btn,.runbtn,button{width:100%;min-height:46px}pre,.report{max-height:58vh}.mini-grid{grid-template-columns:1fr}.chart-wrap{padding:8px}.chart-controls{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.chart-range{padding:9px 6px;text-align:center}}.card{background:rgba(17,23,34,.88);border:1px solid var(--line);border-radius:22px;padding:22px;box-shadow:0 20px 70px rgba(0,0,0,.26);margin-bottom:20px}label{display:block;color:#c8d2e3;font-weight:700;margin:14px 0 6px}input,select{width:100%;border:1px solid #334158;border-radius:12px;background:#0a0f17;color:var(--text);padding:12px 13px;font:inherit;min-height:46px}select{appearance:auto}.customTicker{display:none;margin-top:8px}.customTicker.show{display:block}.formhint{margin:6px 0 0;color:#91a0b7;font-size:12px}.checks{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:6px}.check{border:1px solid #334158;border-radius:12px;padding:10px;background:#0a0f17}.check input{width:auto;margin-right:7px}button,.btn{display:inline-block;text-align:center;text-decoration:none;margin-top:12px;border:0;border-radius:14px;background:linear-gradient(135deg,#d9a441,#ffdc7d);color:#130d02;font-weight:900;padding:12px 14px;font:inherit;cursor:pointer}.btn.secondary{background:#0a0f17;color:#ffd47a;border:1px solid #334158}.btnrow{display:flex;gap:10px;flex-wrap:wrap}.runbtn{width:100%}button:disabled{filter:grayscale(1);opacity:.55;cursor:not-allowed}.muted{color:var(--muted);font-size:14px}.status{display:inline-flex;align-items:center;gap:8px;border:1px solid #334158;background:#0a0f17;border-radius:999px;padding:7px 11px;color:var(--muted);font-size:14px}.dot{width:9px;height:9px;border-radius:99px;background:var(--muted)}.running .dot{background:var(--gold);box-shadow:0 0 18px var(--gold)}.done .dot{background:var(--ok)}.failed .dot{background:var(--bad)}pre{white-space:pre-wrap;word-break:break-word;background:#05070b;border:1px solid #1b2638;border-radius:16px;padding:16px;max-height:680px;overflow:auto}.result{min-height:260px}.decision{border-left:4px solid var(--gold);padding-left:14px;margin:18px 0}.decision-hero{display:grid;grid-template-columns:260px 1fr;gap:18px;align-items:stretch;border-width:2px;position:relative;overflow:hidden}.decision-hero:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 0% 0%,var(--decision-glow),transparent 30rem);pointer-events:none}.decision-hero>*{position:relative}.verdict-box{border:1px solid var(--decision-border);background:var(--decision-bg);border-radius:18px;padding:18px;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;min-height:150px}.verdict-label{font-size:12px;color:var(--muted);font-weight:900;text-transform:uppercase;letter-spacing:.14em}.verdict{font-size:clamp(34px,5vw,58px);font-weight:1000;letter-spacing:-.05em;line-height:.95;color:var(--decision-color);text-transform:uppercase;text-shadow:0 0 24px var(--decision-glow)}.verdict-ticker{font-size:18px;font-weight:900;color:#fff;margin-top:10px}.decision-summary{font-size:18px;color:#e8eefb}.decision-summary strong{color:#fff}.decision-actions{margin-top:10px;color:var(--muted)}.tone-buy{--decision-color:#46d17d;--decision-border:#276f43;--decision-bg:rgba(70,209,125,.10);--decision-glow:rgba(70,209,125,.24)}.tone-hold{--decision-color:#ffd47a;--decision-border:#8a6521;--decision-bg:rgba(217,164,65,.12);--decision-glow:rgba(217,164,65,.24)}.tone-sell{--decision-color:#ff6b6b;--decision-border:#8a3030;--decision-bg:rgba(255,107,107,.12);--decision-glow:rgba(255,107,107,.24)}.tone-neutral{--decision-color:#91a0b7;--decision-border:#334158;--decision-bg:rgba(145,160,183,.10);--decision-glow:rgba(145,160,183,.18)}.mini-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}.mini-card{border:1px solid #334158;background:#0a0f17;border-radius:14px;padding:12px}.mini-label{font-size:11px;color:#91a0b7;text-transform:uppercase;letter-spacing:.10em;font-weight:900}.mini-value{font-size:18px;font-weight:900;color:#fff;margin-top:4px}.resource-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}.resource-pill{border:1px solid #334158;background:#05070b;border-radius:999px;padding:6px 10px;font-size:13px;color:#c8d2e3}.resource-pill.on{border-color:#d9a441;color:#ffd47a;background:#2b1d08}.resource-pill.present{border-color:#46d17d;color:#8dffb7;background:rgba(70,209,125,.08)}.chart-controls{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 14px}.chart-range{border:1px solid #334158;background:#0a0f17;color:#ffd47a;border-radius:999px;padding:7px 11px;cursor:pointer}.chart-range.active{background:#2b1d08;border-color:#d9a441}.chart-wrap{background:#05070b;border:1px solid #1b2638;border-radius:16px;padding:12px;overflow:hidden}.chart-svg{width:100%;height:auto;display:block}.chart-summary{border-left:4px solid var(--decision-color,#d9a441);padding-left:12px;color:#e8eefb;margin:12px 0}.legend{display:flex;gap:10px;flex-wrap:wrap;color:#91a0b7;font-size:12px}.legend span:before{content:"";display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;background:var(--c)}@media(max-width:700px){.decision-hero{grid-template-columns:1fr}.verdict-box{min-height:auto}.verdict{font-size:40px}.decision-summary{font-size:16px}.table th,.table td{padding:8px}.resource-list{gap:6px}.resource-pill{font-size:12px}.tabs{display:grid;grid-template-columns:1fr 1fr}.tab{padding:10px 8px}}.tiny{font-size:12px;color:#738198}a{color:#ffd47a}.table{width:100%;border-collapse:collapse}.table th,.table td{border-bottom:1px solid #243044;padding:10px;text-align:left;vertical-align:top}.pill{display:inline-block;border:1px solid #334158;border-radius:999px;padding:3px 8px;font-size:12px;color:#c8d2e3;background:#0a0f17}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}.tab{border:1px solid #334158;background:#0a0f17;color:#ffd47a;border-radius:999px;padding:8px 11px;cursor:pointer}.tab.active{background:#2b1d08;border-color:#d9a441}.section{display:none}.section.active{display:block}.report{white-space:pre-wrap;background:#05070b;border:1px solid #1b2638;border-radius:16px;padding:16px;max-height:780px;overflow:auto}.danger{color:#ff9b9b}.ok{color:#8dffb7}
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def html_escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def parse_holdings_tickers(markdown: str) -> list[str]:
    in_holdings = False
    ticker_col: int | None = None
    tickers: list[str] = []
    seen: set[str] = set()
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_holdings = stripped.lower() == "## holdings"
            ticker_col = None
            continue
        if not in_holdings or not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if ticker_col is None:
            headers = [cell.lower() for cell in cells]
            if "ticker" not in headers:
                continue
            ticker_col = headers.index("ticker")
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if ticker_col >= len(cells):
            continue
        ticker = cells[ticker_col].upper()
        if TICKER_RE.match(ticker) and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def portfolio_tickers(path: Path = PORTFOLIO_PATH) -> list[str]:
    try:
        tickers = parse_holdings_tickers(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_PORTFOLIO_TICKERS.copy()
    return tickers or DEFAULT_PORTFOLIO_TICKERS.copy()


def safe_run_id(run_id: str) -> str:
    if not re.match(r"^[A-Za-z0-9_.:-]{1,80}$", run_id):
        raise ValueError("invalid run id")
    return run_id


def run_dir(run_id: str) -> Path:
    return RUNS_DIR / safe_run_id(run_id)


def meta_path(run_id: str) -> Path:
    return run_dir(run_id) / "meta.json"


def stdout_path(run_id: str) -> Path:
    return run_dir(run_id) / "stdout.txt"


def report_path(run_id: str) -> Path:
    return run_dir(run_id) / "report.md"


def state_path_from_output(output: str) -> str:
    match = re.search(r"Full state log:\s*(.+)", output)
    if not match:
        return ""
    raw = match.group(1).strip()
    if raw.startswith("~/"):
        return str(Path.home() / raw[2:])
    return raw


def extract_decision(output: str) -> str:
    marker = "=== PARSED DECISION ==="
    next_marker = "=== FINAL TRADE DECISION ==="
    if marker in output:
        part = output.split(marker, 1)[1]
        if next_marker in part:
            return part.split(next_marker, 1)[0].strip()
        return part.strip()
    return ""


def read_json_file(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def write_json_file(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def load_meta(run_id: str) -> dict[str, object] | None:
    p = meta_path(run_id)
    if not p.exists():
        return None
    data = read_json_file(p)
    if data:
        data.setdefault("id", run_id)
    return data or None


def save_meta(run_id: str, updates: dict[str, object]) -> dict[str, object]:
    run_dir(run_id).mkdir(parents=True, exist_ok=True)
    data = load_meta(run_id) or {"id": run_id, "created_at": now_iso()}
    data.update(updates)
    data["updated_at"] = now_iso()
    write_json_file(meta_path(run_id), data)
    return data


def parse_iso_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def normalized_state_path(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return os.path.normcase(os.path.abspath(os.path.expanduser(raw)))


def is_imported_run(meta: dict[str, object]) -> bool:
    return bool(meta.get("imported")) or str(meta.get("id", "")).startswith("imported-")


def run_ticker_date_key(meta: dict[str, object]) -> tuple[str, str]:
    return (str(meta.get("ticker") or "").upper(), str(meta.get("date") or ""))


def read_all_run_metas() -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    for p in RUNS_DIR.glob("*/meta.json"):
        data = read_json_file(p)
        if data:
            data.setdefault("id", p.parent.name)
            runs.append(data)
    return runs


def imported_run_has_ui_duplicate(imported: dict[str, object], runs: list[dict[str, object]]) -> bool:
    import_state_path = normalized_state_path(imported.get("state_path"))
    import_key = run_ticker_date_key(imported)
    for run in runs:
        if is_imported_run(run):
            continue
        if import_state_path and normalized_state_path(run.get("state_path")) == import_state_path:
            return True
        if import_key[0] and import_key[1] and run_ticker_date_key(run) == import_key:
            return True
    return False


def stale_run_has_newer_success(run: dict[str, object], runs: list[dict[str, object]]) -> bool:
    if is_imported_run(run) or str(run.get("status") or "") != "failed":
        return False
    if "UI service restarted" not in str(run.get("error") or ""):
        return False
    key = run_ticker_date_key(run)
    if not key[0] or not key[1]:
        return False
    created = parse_iso_datetime(run.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
    for other in runs:
        if other is run or is_imported_run(other):
            continue
        if run_ticker_date_key(other) != key or str(other.get("status") or "") != "done":
            continue
        other_created = parse_iso_datetime(other.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if other_created >= created:
            return True
    return False


def visible_history_runs(runs: list[dict[str, object]]) -> list[dict[str, object]]:
    visible: list[dict[str, object]] = []
    for run in runs:
        if is_imported_run(run) and imported_run_has_ui_duplicate(run, runs):
            continue
        if stale_run_has_newer_success(run, runs):
            continue
        visible.append(run)
    visible.sort(key=lambda r: str(r.get("created_at") or r.get("updated_at") or ""), reverse=True)
    return visible


def run_has_final_artifact(run_id: str, meta: dict[str, object]) -> bool:
    state_path = normalized_state_path(meta.get("state_path"))
    return bool(state_path and Path(state_path).exists()) or report_path(run_id).exists()


def reconcile_stale_jobs() -> None:
    now = datetime.now(timezone.utc)
    for meta in read_all_run_metas():
        status = str(meta.get("status") or "")
        if status not in {"queued", "running"}:
            continue
        run_id = str(meta.get("id") or "")
        if not run_id:
            continue
        with JOBS_LOCK:
            in_memory = run_id in JOBS
        if in_memory:
            continue
        started = parse_iso_datetime(meta.get("started_at")) or parse_iso_datetime(meta.get("updated_at")) or parse_iso_datetime(meta.get("created_at"))
        if not started or (now - started).total_seconds() < STALE_JOB_SECONDS:
            continue
        if run_has_final_artifact(run_id, meta):
            continue
        error = "UI service restarted while this run was queued/running; no active job, final state, or final report was found."
        stdout = stdout_path(run_id).read_text(errors="replace") if stdout_path(run_id).exists() else ""
        if stdout and error not in stdout:
            stdout += f"\nERROR: {error}\n"
            stdout_path(run_id).write_text(stdout)
        elif not stdout:
            stdout = f"ERROR: {error}\n"
            stdout_path(run_id).write_text(stdout)
        updated = save_meta(run_id, {"status": "failed", "finished_at": now_iso(), "error": error, "decision": extract_decision(stdout)})
        report_path(run_id).write_text(generate_report(updated, load_state(updated), stdout))


def discover_state_logs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    existing_runs = read_all_run_metas()
    for path in LOGS_DIR.glob("*/TradingAgentsStrategy_logs/full_states_log_*.json"):
        try:
            state = read_json_file(path)
            ticker = str(state.get("company_of_interest") or path.parents[1].name).upper()
            trade_date = str(state.get("trade_date") or path.stem.replace("full_states_log_", ""))
            digest = hashlib.sha1(str(path).encode()).hexdigest()[:10]
            run_id = f"imported-{ticker}-{trade_date}-{digest}"
            if meta_path(run_id).exists():
                continue
            meta = {
                "id": run_id,
                "created_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
                "updated_at": now_iso(),
                "ticker": ticker,
                "date": trade_date,
                "analysts": "imported",
                "model": "unknown",
                "status": "done",
                "exit_code": 0,
                "decision": str(state.get("final_trade_decision") or state.get("trader_investment_decision") or "")[:4000],
                "state_path": str(path),
                "imported": True,
            }
            if imported_run_has_ui_duplicate(meta, existing_runs):
                continue
            save_meta(run_id, meta)
            existing_runs.append(meta)
            report_path(run_id).write_text(generate_report(meta, state))
        except Exception:
            continue


def list_runs() -> list[dict[str, object]]:
    discover_state_logs()
    reconcile_stale_jobs()
    return visible_history_runs(read_all_run_metas())


def load_state(meta: dict[str, object]) -> dict[str, object]:
    sp = str(meta.get("state_path") or "")
    if not sp:
        return {}
    p = Path(sp).expanduser()
    if not p.exists():
        return {}
    return read_json_file(p)


def md_block(title: str, value: object) -> str:
    if value in (None, "", {}, []):
        return f"## {title}\n\n_Not available for this run._\n"
    if isinstance(value, dict):
        lines = [f"## {title}\n"]
        for key, item in value.items():
            pretty_key = str(key).replace("_", " ").title()
            lines.append(f"### {pretty_key}\n\n{item or '_Not available._'}\n")
        return "\n".join(lines)
    return f"## {title}\n\n{value}\n"


def plain_text(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"[*_`#>]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def decision_snapshot(final_decision: object, ticker: object = "") -> dict[str, str]:
    text = str(final_decision or "").strip()
    compact = plain_text(text)
    upper = compact.upper()
    verdict = "UNKNOWN"
    tone = "neutral"
    candidates = [
        ("STRONG BUY", "BUY", "buy"),
        ("OVERWEIGHT", "OVERWEIGHT", "buy"),
        ("BUY", "BUY", "buy"),
        ("ACCUMULATE", "BUY", "buy"),
        ("HOLD", "HOLD", "hold"),
        ("NEUTRAL", "HOLD", "hold"),
        ("WAIT", "HOLD", "hold"),
        ("UNDERWEIGHT", "UNDERWEIGHT", "sell"),
        ("REDUCE", "SELL", "sell"),
        ("SELL", "SELL", "sell"),
        ("SHORT", "SELL", "sell"),
    ]
    for token, label, found_tone in candidates:
        if re.search(rf"\b{re.escape(token)}\b", upper):
            verdict = label
            tone = found_tone
            break

    lines = [ln.strip(" -*•\t") for ln in text.splitlines() if ln.strip()]
    first_line = plain_text(lines[0]) if lines else ""
    explanation = ""
    for line in lines[1:]:
        clean = plain_text(line)
        if not clean or clean.lower() in {"why:", "decision:", "bottom line:"}:
            continue
        if len(clean) > 35:
            explanation = clean
            break
    if not explanation:
        sentences = re.split(r"(?<=[.!?])\s+", compact)
        explanation = next((x for x in sentences if len(x) > 35 and verdict not in x.upper()[:25]), "")
    if not explanation:
        explanation = "Read the full report below for the detailed reasoning behind this call."
    if len(explanation) > 280:
        explanation = explanation[:277].rsplit(" ", 1)[0] + "…"

    action = {
        "buy": "Bias is constructive. Confirm sizing and risk before acting.",
        "hold": "Bias is patient. Keep/observe; avoid forcing a new trade without a better setup.",
        "sell": "Bias is defensive. Review exposure and risk limits before acting.",
        "neutral": "Decision could not be cleanly classified. Read the report before acting.",
    }[tone]

    return {
        "verdict": verdict,
        "tone": tone,
        "headline": first_line or f"{ticker}: {verdict}",
        "explanation": explanation,
        "action": action,
    }


def parse_proxy_metrics(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or " " not in line:
            continue
        name, value = line.rsplit(" ", 1)
        try:
            val = float(value)
        except ValueError:
            continue
        if name.startswith("codex_proxy_requests_total"):
            metrics["requests_total"] = metrics.get("requests_total", 0.0) + val
        elif name.startswith("codex_proxy_request_duration_seconds_sum"):
            metrics["request_seconds_sum"] = metrics.get("request_seconds_sum", 0.0) + val
        elif name.startswith("codex_proxy_turn_duration_ms") and name.endswith("_sum"):
            metrics["turn_ms_sum"] = metrics.get("turn_ms_sum", 0.0) + val
        elif name.startswith("codex_proxy_turn_duration_ms") and name.endswith("_count"):
            metrics["turn_count"] = metrics.get("turn_count", 0.0) + val
        elif name.startswith("codex_proxy_tokens_total"):
            if 'direction="total"' in name:
                metrics["tokens_total"] = metrics.get("tokens_total", 0.0) + val
            elif 'direction="input"' in name:
                metrics["input_tokens"] = metrics.get("input_tokens", 0.0) + val
            elif 'direction="output"' in name:
                metrics["output_tokens"] = metrics.get("output_tokens", 0.0) + val
            elif 'direction="cached_input"' in name:
                metrics["cached_input_tokens"] = metrics.get("cached_input_tokens", 0.0) + val
        elif name.startswith("codex_proxy_estimated_cost_usd_total"):
            metrics["estimated_cost_usd"] = metrics.get("estimated_cost_usd", 0.0) + val
    return metrics


def fetch_proxy_metrics() -> dict[str, float]:
    try:
        with urllib.request.urlopen("http://127.0.0.1:3466/metrics", timeout=3) as response:
            return parse_proxy_metrics(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}


def metric_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    keys = set(before) | set(after)
    return {k: round(after.get(k, 0.0) - before.get(k, 0.0), 3) for k in keys if round(after.get(k, 0.0) - before.get(k, 0.0), 3) != 0}


def format_duration(meta: dict[str, object]) -> str:
    try:
        start = datetime.fromisoformat(str(meta.get("started_at", "")).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(meta.get("finished_at", "")).replace("Z", "+00:00"))
        seconds = int((end - start).total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        return f"{seconds // 60}m {seconds % 60}s"
    except Exception:
        return "n/a"


def requested_resources(meta: dict[str, object]) -> list[str]:
    raw = str(meta.get("analysts") or "")
    if raw == "imported":
        return ["imported / unknown"]
    return [x.strip() for x in raw.split(",") if x.strip()] or ["market"]


def present_resources(state: dict[str, object]) -> list[str]:
    mapping = {
        "market_report": "market",
        "sentiment_report": "social",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "investment_debate_state": "investment debate",
        "risk_debate_state": "risk debate",
    }
    return [label for key, label in mapping.items() if state.get(key)]


def usage_summary(meta: dict[str, object]) -> dict[str, str]:
    raw_delta = meta.get("proxy_metrics_delta")
    delta = raw_delta if isinstance(raw_delta, dict) else {}
    requests = delta.get("requests_total")
    seconds = delta.get("request_seconds_sum")
    turns = delta.get("turn_count")
    tokens = delta.get("tokens_total") or meta.get("total_tokens")
    input_tokens = delta.get("input_tokens")
    output_tokens = delta.get("output_tokens")
    cost = delta.get("estimated_cost_usd") or meta.get("total_cost")
    token_text = "not captured"
    if isinstance(tokens, (int, float)) and tokens > 0:
        parts = [f"{int(tokens):,} total"]
        if isinstance(input_tokens, (int, float)) and input_tokens > 0:
            parts.append(f"{int(input_tokens):,} input")
        if isinstance(output_tokens, (int, float)) and output_tokens > 0:
            parts.append(f"{int(output_tokens):,} output")
        token_text = " · ".join(parts)
    return {
        "requests": str(int(requests)) if isinstance(requests, (int, float)) and requests > 0 else "not captured",
        "proxy_seconds": f"{seconds:.1f}s" if isinstance(seconds, (int, float)) and seconds > 0 else "not captured",
        "turns": str(int(turns)) if isinstance(turns, (int, float)) and turns > 0 else "not captured",
        "tokens": token_text,
        "cost": f"~${float(cost):.4f} simulated API cost" if isinstance(cost, (int, float)) and cost > 0 else "not captured yet; future runs estimate from public API prices",
    }


def resource_usage_html(meta: dict[str, object], state: dict[str, object]) -> str:
    requested = requested_resources(meta)
    present = present_resources(state)
    requested_html = "".join(f'<span class="resource-pill on">{html_escape(x)}</span>' for x in requested)
    present_html = "".join(f'<span class="resource-pill present">{html_escape(x)}</span>' for x in present) or '<span class="resource-pill">none found in state</span>'
    usage = usage_summary(meta)
    return f'''<div class="card"><h2>Run inputs & cost</h2><p class="muted">What was selected before the analysis and what the runner/proxy reported afterward.</p><h3>Requested resources</h3><div class="resource-list">{requested_html}</div><h3 style="margin-top:18px">Reports present in saved state</h3><div class="resource-list">{present_html}</div><div class="mini-grid"><div class="mini-card"><div class="mini-label">Model</div><div class="mini-value">{html_escape(meta.get('model') or 'unknown')}</div></div><div class="mini-card"><div class="mini-label">Duration</div><div class="mini-value">{html_escape(format_duration(meta))}</div></div><div class="mini-card"><div class="mini-label">Proxy calls</div><div class="mini-value">{html_escape(usage['requests'])}</div></div><div class="mini-card"><div class="mini-label">Proxy time</div><div class="mini-value">{html_escape(usage['proxy_seconds'])}</div></div></div><p class="muted"><strong>Tokens:</strong> {html_escape(usage['tokens'])}<br><strong>Cost:</strong> {html_escape(usage['cost'])}</p></div>'''


def period_for_range(range_key: str) -> tuple[str, int]:
    mapping = {
        "1m": ("1y", 31),
        "3m": ("1y", 93),
        "6m": ("1y", 186),
        "1y": ("18mo", 370),
    }
    return mapping.get(range_key, mapping["6m"])


def rsi_series(closes, window: int = 14):
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def chart_summary(ticker: str, verdict: str, latest: dict[str, object]) -> str:
    close = latest.get("close")
    ma20 = latest.get("ma20")
    ma50 = latest.get("ma50")
    ma200 = latest.get("ma200")
    rsi = latest.get("rsi")
    parts: list[str] = []
    try:
        if close and ma20 and ma50:
            if close > ma20 > ma50:
                parts.append("price is above the 20- and 50-day trend lines")
            elif close < ma20 < ma50:
                parts.append("price is below short- and medium-term trend lines")
            else:
                parts.append("price is mixed around the short/medium trend lines")
        if close and ma200:
            parts.append("above the 200-day long-term trend" if close > ma200 else "below the 200-day long-term trend")
        if rsi:
            if rsi >= 70:
                parts.append("RSI is stretched/overbought")
            elif rsi <= 30:
                parts.append("RSI is oversold")
            else:
                parts.append("RSI is neutral")
    except Exception:
        pass
    evidence = "; ".join(parts) or "the chart provides trend and momentum context"
    v = verdict.upper()
    if v in {"BUY", "OVERWEIGHT"}:
        return f"Chart read for {ticker}: {evidence}. This helps explain a constructive call, while still showing where momentum may be stretched."
    if v in {"SELL", "UNDERWEIGHT"}:
        return f"Chart read for {ticker}: {evidence}. This helps explain a defensive call and highlights where trend/risk may be breaking down."
    if v == "HOLD":
        return f"Chart read for {ticker}: {evidence}. This supports a patient HOLD-style call when quality/trend exists but entry risk or momentum stretch argues against chasing."
    return f"Chart read for {ticker}: {evidence}. Use this as visual context for the final decision above."


def get_chart_data(ticker: str, range_key: str, verdict: str) -> dict[str, object]:
    try:
        import yfinance as yf
    except Exception as exc:
        return {"error": f"yfinance unavailable: {exc}"}
    period, keep_days = period_for_range(range_key)
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=False, threads=False)
        if df is None or df.empty:
            return {"error": f"No chart data returned for {ticker}"}
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = [c[0] for c in df.columns]
        close_col = "Adj Close" if "Adj Close" in df.columns else "Close"
        df = df.rename(columns={close_col: "close", "Open": "open", "High": "high", "Low": "low", "Volume": "volume"})
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma50"] = df["close"].rolling(50).mean()
        df["ma200"] = df["close"].rolling(200).mean()
        df["rsi"] = rsi_series(df["close"])
        sliced = df.tail(keep_days)
        rows: list[dict[str, object]] = []
        for idx, row in sliced.iterrows():
            item: dict[str, object] = {"date": idx.strftime("%Y-%m-%d")}
            for key in ["open", "high", "low", "close", "volume", "ma20", "ma50", "ma200", "rsi"]:
                val = row.get(key)
                if val != val or val is None:
                    item[key] = None
                else:
                    item[key] = round(float(val), 4) if key != "volume" else int(val)
            rows.append(item)
        latest = next((r for r in reversed(rows) if r.get("close")), {})
        return {"ticker": ticker, "range": range_key, "verdict": verdict, "rows": rows, "latest": latest, "summary": chart_summary(ticker, verdict, latest)}
    except Exception as exc:
        return {"error": f"Chart data failed: {exc}"}


def chart_panel_html(run_id: str, ticker: object, verdict: str) -> str:
    rid = html_escape(run_id)
    tick = html_escape(ticker or "")
    ver = html_escape(verdict or "UNKNOWN")
    return f'''<div class="card chart-card" data-run-id="{rid}" data-ticker="{tick}" data-verdict="{ver}"><h2>Decision chart</h2><p class="muted">Price, moving averages, RSI, volume, and the final decision marker. Use ranges to see short- and longer-term context.</p><div class="chart-controls"><button class="chart-range" data-range="1m">1M</button><button class="chart-range" data-range="3m">3M</button><button class="chart-range active" data-range="6m">6M</button><button class="chart-range" data-range="1y">1Y</button></div><div class="legend"><span style="--c:#edf2ff">Close</span><span style="--c:#46d17d">MA20</span><span style="--c:#ffd47a">MA50</span><span style="--c:#ff6b6b">MA200</span><span style="--c:#7aa2ff">RSI</span><span style="--c:#5d6b84">Volume</span></div><div id="chart-summary-{rid}" class="chart-summary">Loading chart…</div><div id="chart-{rid}" class="chart-wrap"></div></div>'''


def generate_report(meta: dict[str, object], state: dict[str, object] | None = None, stdout: str = "") -> str:
    state = state or load_state(meta)
    ticker = meta.get("ticker") or state.get("company_of_interest") or "UNKNOWN"
    trade_date = meta.get("date") or state.get("trade_date") or "UNKNOWN"
    parts = [
        f"# TradingAgents Report — {ticker} / {trade_date}\n",
        "**Research-only. Not financial advice. No broker integration. No order execution.**\n",
        f"- Run ID: `{meta.get('id', '')}`",
        f"- Status: `{meta.get('status', '')}`",
        f"- Model: `{meta.get('model', '')}`",
        f"- Analysts: `{meta.get('analysts', '')}`",
        f"- Created: `{meta.get('created_at', '')}`",
        f"- State log: `{meta.get('state_path', '')}`\n",
        md_block("Final Trade Decision", state.get("final_trade_decision") or meta.get("decision")),
        md_block("Parsed Decision", meta.get("decision")),
        md_block("Market Report", state.get("market_report")),
        md_block("Sentiment Report", state.get("sentiment_report")),
        md_block("News Report", state.get("news_report")),
        md_block("Fundamentals Report", state.get("fundamentals_report")),
        md_block("Investment Debate", state.get("investment_debate_state")),
        md_block("Trader Investment Decision", state.get("trader_investment_decision")),
        md_block("Risk Debate", state.get("risk_debate_state")),
        md_block("Investment Plan", state.get("investment_plan")),
    ]
    if stdout:
        parts.append("## Raw Runner Output\n\n```text\n" + stdout[-20000:] + "\n```\n")
    return "\n".join(parts)


def page() -> bytes:
    today = date.today().isoformat()
    checks = "".join(
        f'<label class="check"><input type="checkbox" name="analysts" value="{a}" checked> {a.title()}</label>'
        for a in ANALYSTS
    )
    models = "".join(f'<option value="{m}">{m}</option>' for m in MODELS)
    ticker_options = "".join(f'<option value="{html_escape(ticker)}" {"selected" if ticker == "AAPL" else ""}>{html_escape(ticker)}</option>' for ticker in portfolio_tickers())
    body = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TradingAgents — Reaper</title><style>{STYLE}</style></head><body><main><section class="hero"><div class="sigil">⚔️</div><div><h1>TradingAgents</h1><p class="sub">Codex-powered market research archive. No broker. No real-money execution.</p></div></section><section class="grid"><form id="runForm" class="card"><h2>Run analysis</h2><label>Ticker</label><select id="tickerSelect" name="ticker_select" aria-label="Portfolio ticker"><option value="">Choose from portfolio…</option>{ticker_options}<option value="__custom__">Other ticker…</option></select><div id="customTickerWrap" class="customTicker"><input id="customTicker" name="ticker_custom" value="" maxlength="12" autocomplete="off" placeholder="Type ticker, e.g. TSLA"></div><p class="formhint">Pick a portfolio ticker or choose “Other ticker…” to type any symbol.</p><label>Analysis date</label><input name="date" type="date" value="{today}" required><label>Analysts</label><div class="checks">{checks}</div><label>Model</label><select name="model">{models}</select><label>Timeout</label><select name="timeout"><option value="900">15 minutes</option><option value="1800" selected>30 minutes</option><option value="3600">60 minutes</option></select><button class="runbtn" id="runBtn" type="submit">Run analysis</button><p class="muted">Every run is saved under <code>~/.tradingagents/ui_runs</code>. Full state logs remain under <code>~/.tradingagents/logs</code>.</p></form><section class="card result"><div id="status" class="status"><span class="dot"></span><span>Idle</span></div><div id="decision" class="decision" style="display:none"></div><pre id="output">Ready.</pre><p class="tiny">Public path: OVH DNS → AWS nginx → reverse SSH tunnel → Mac UI.</p></section></section><section class="card"><h2>Run history</h2><p class="muted">Includes UI runs plus imported TradingAgents full-state logs.</p><div id="history">Loading…</div></section></main><script>
const form=document.getElementById('runForm'), btn=document.getElementById('runBtn'), out=document.getElementById('output'), statusBox=document.getElementById('status'), decision=document.getElementById('decision'), historyBox=document.getElementById('history'), tickerSelect=document.getElementById('tickerSelect'), customTickerWrap=document.getElementById('customTickerWrap'), customTicker=document.getElementById('customTicker');
function syncTickerInput(){{const custom=tickerSelect.value==='__custom__'; customTickerWrap.classList.toggle('show', custom); customTicker.required=custom; if(custom) customTicker.focus();}}
tickerSelect.addEventListener('change', syncTickerInput);
syncTickerInput();
function setStatus(s, text){{statusBox.className='status '+s; statusBox.querySelector('span:last-child').textContent=text;}}
function escapeHtml(s){{return String(s||'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));}}
function renderHistory(runs){{ if(!runs.length){{historyBox.innerHTML='<p class="muted">No runs yet.</p>';return;}} historyBox.innerHTML='<table class="table"><thead><tr><th>Run</th><th>Status</th><th>Model</th><th>Created</th><th></th></tr></thead><tbody>'+runs.map(r=>`<tr><td><strong>${{escapeHtml(r.ticker)}} / ${{escapeHtml(r.date)}}</strong><br><span class="tiny">${{escapeHtml(r.id)}}</span></td><td><span class="pill">${{escapeHtml(r.status)}}</span></td><td>${{escapeHtml(r.model||'')}}</td><td>${{escapeHtml(r.created_at||'')}}</td><td><a class="btn secondary" href="/run/${{encodeURIComponent(r.id)}}">Open</a></td></tr>`).join('')+'</tbody></table>';}}
async function loadHistory(){{ const r=await fetch('/api/runs'); renderHistory(await r.json()); }}
async function poll(id){{
  const r=await fetch('/api/run/'+id); const j=await r.json();
  setStatus(j.status, j.status==='running'?'Running…':(j.status==='done'?'Done':(j.status==='failed'?'Failed':'Idle')));
  out.textContent=j.output || '';
  if(j.decision){{decision.style.display='block'; decision.innerHTML='<h3>Decision</h3><pre>'+escapeHtml(j.decision)+'</pre><p><a class="btn secondary" href="/run/'+encodeURIComponent(id)+'">Open full run</a></p>';}}
  await loadHistory();
  if(j.status==='running' || j.status==='queued') setTimeout(()=>poll(id), 2000); else btn.disabled=false;
}}
form.addEventListener('submit', async e=>{{
  e.preventDefault(); btn.disabled=true; decision.style.display='none'; out.textContent='Starting…'; setStatus('running','Starting…');
  const data=new FormData(form); const analysts=data.getAll('analysts'); data.delete('analysts'); data.set('analysts', analysts.join(',')); const selectedTicker=tickerSelect.value==='__custom__'?customTicker.value:tickerSelect.value; data.set('ticker', selectedTicker); data.delete('ticker_select'); data.delete('ticker_custom');
  const r=await fetch('/api/run', {{method:'POST', body:new URLSearchParams(data)}}); const j=await r.json();
  if(!r.ok){{setStatus('failed','Failed'); out.textContent=j.error || 'Request failed'; btn.disabled=false; return;}}
  poll(j.id);
}});
loadHistory();
</script></body></html>"""
    return body.encode("utf-8")


TAB_SCRIPT = "<script>document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab,.section').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active');});</script>"
CHART_SCRIPT = '<script>\nfunction esc(s){return String(s??\'\').replace(/[&<>"\']/g,c=>({\'&\':\'&amp;\',\'<\':\'&lt;\',\'>\':\'&gt;\',\'"\':\'&quot;\',"\'":\'&#39;\'}[c]));}\nfunction toneColor(v){v=String(v||\'\').toUpperCase(); if(v.includes(\'SELL\')||v.includes(\'UNDER\')) return \'#ff6b6b\'; if(v.includes(\'BUY\')||v.includes(\'OVER\')) return \'#46d17d\'; if(v.includes(\'HOLD\')||v.includes(\'NEUTRAL\')) return \'#ffd47a\'; return \'#91a0b7\';}\nfunction points(rows,key,x,y){return rows.map((r,i)=>r[key]==null?null:[x(i),y(r[key])]).filter(Boolean).map(p=>p.join(\',\')).join(\' \')}\nfunction drawChart(target,data){\n const el=document.getElementById(target); if(!el) return;\n if(data.error){el.innerHTML=\'<p class="danger">\'+esc(data.error)+\'</p>\'; return;}\n const rows=(data.rows||[]).filter(r=>r.close!=null); if(rows.length<2){el.innerHTML=\'<p class="muted">Not enough chart data.</p>\'; return;}\n const W=980,H=520,pad=46,priceH=270,rsiTop=310,rsiH=80,volTop=420,volH=70;\n const prices=[]; rows.forEach(r=>[\'close\',\'ma20\',\'ma50\',\'ma200\'].forEach(k=>{if(r[k]!=null)prices.push(r[k])}));\n const minP=Math.min(...prices), maxP=Math.max(...prices), spanP=(maxP-minP)||1;\n const maxV=Math.max(...rows.map(r=>r.volume||0),1);\n const x=i=>pad+(i/(rows.length-1))*(W-pad*2);\n const yP=v=>pad+(maxP-v)/spanP*(priceH-pad);\n const yR=v=>rsiTop+(100-v)/100*rsiH;\n const yV=v=>volTop+volH-(v/maxV)*volH;\n const closePts=points(rows,\'close\',x,yP), ma20=points(rows,\'ma20\',x,yP), ma50=points(rows,\'ma50\',x,yP), ma200=points(rows,\'ma200\',x,yP), rsi=points(rows,\'rsi\',x,yR);\n const bars=rows.map((r,i)=>`<line x1="${x(i).toFixed(1)}" x2="${x(i).toFixed(1)}" y1="${yV(r.volume||0).toFixed(1)}" y2="${(volTop+volH).toFixed(1)}" stroke="#5d6b84" stroke-width="2" opacity=".55"/>`).join(\'\');\n const last=rows[rows.length-1], lx=x(rows.length-1), ly=yP(last.close), c=toneColor(data.verdict);\n const grid=[0,.25,.5,.75,1].map(t=>`<line x1="${pad}" x2="${W-pad}" y1="${(pad+t*(priceH-pad)).toFixed(1)}" y2="${(pad+t*(priceH-pad)).toFixed(1)}" stroke="#1b2638"/>`).join(\'\');\n const labels=`<text x="${pad}" y="24" fill="#91a0b7" font-size="12">${esc(data.ticker)} ${esc(data.range)} · latest $${Number(last.close).toFixed(2)}</text><text x="${W-pad}" y="24" fill="${c}" font-size="13" font-weight="900" text-anchor="end">${esc(data.verdict)}</text><text x="${pad}" y="${rsiTop-8}" fill="#91a0b7" font-size="12">RSI</text><text x="${pad}" y="${volTop-8}" fill="#91a0b7" font-size="12">Volume</text><text x="${pad}" y="${H-12}" fill="#738198" font-size="11">${esc(rows[0].date)}</text><text x="${W-pad}" y="${H-12}" fill="#738198" font-size="11" text-anchor="end">${esc(last.date)}</text>`;\n el.innerHTML=`<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(data.ticker)} price chart">${grid}<polyline points="${closePts}" fill="none" stroke="#edf2ff" stroke-width="2.4"/><polyline points="${ma20}" fill="none" stroke="#46d17d" stroke-width="1.4" opacity=".9"/><polyline points="${ma50}" fill="none" stroke="#ffd47a" stroke-width="1.4" opacity=".9"/><polyline points="${ma200}" fill="none" stroke="#ff6b6b" stroke-width="1.4" opacity=".9"/><line x1="${pad}" x2="${W-pad}" y1="${yR(70)}" y2="${yR(70)}" stroke="#8a6521" stroke-dasharray="5 5"/><line x1="${pad}" x2="${W-pad}" y1="${yR(30)}" y2="${yR(30)}" stroke="#276f43" stroke-dasharray="5 5"/><polyline points="${rsi}" fill="none" stroke="#7aa2ff" stroke-width="1.8"/>${bars}<line x1="${lx}" x2="${lx}" y1="${pad}" y2="${volTop+volH}" stroke="${c}" stroke-dasharray="6 5" opacity=".9"/><circle cx="${lx}" cy="${ly}" r="7" fill="${c}" stroke="#05070b" stroke-width="3"/><text x="${Math.max(pad+90,lx-8)}" y="${Math.max(42,ly-14)}" fill="${c}" font-size="12" font-weight="900" text-anchor="end">Decision</text>${labels}</svg>`;\n const sum=document.getElementById(\'chart-summary-\'+target.replace(\'chart-\',\'\')); if(sum) sum.textContent=data.summary||\'\';\n}\nasync function loadDecisionChart(card,range){\n const run=card.dataset.runId; const target=\'chart-\'+run; const summary=document.getElementById(\'chart-summary-\'+run); if(summary) summary.textContent=\'Loading chart…\';\n const res=await fetch(\'/api/chart/\'+encodeURIComponent(run)+\'?range=\'+encodeURIComponent(range)); const data=await res.json(); drawChart(target,data);\n}\ndocument.querySelectorAll(\'.chart-card\').forEach(card=>{card.querySelectorAll(\'.chart-range\').forEach(btn=>btn.onclick=()=>{card.querySelectorAll(\'.chart-range\').forEach(b=>b.classList.remove(\'active\'));btn.classList.add(\'active\');loadDecisionChart(card,btn.dataset.range);});loadDecisionChart(card,\'6m\');});\n</script>\n'

def detail_page(run_id: str) -> bytes:
    meta = load_meta(run_id)
    if not meta:
        return b""
    stdout = stdout_path(run_id).read_text(errors="replace") if stdout_path(run_id).exists() else ""
    state = load_state(meta)
    report = report_path(run_id).read_text(errors="replace") if report_path(run_id).exists() else generate_report(meta, state, stdout)
    final_decision = state.get("final_trade_decision") or meta.get("decision") or ""
    snap = decision_snapshot(final_decision, meta.get("ticker") or state.get("company_of_interest") or "")
    state_pretty = json.dumps(state, indent=2, ensure_ascii=False) if state else "No state JSON found for this run."
    resources_panel = resource_usage_html(meta, state)
    chart_panel = chart_panel_html(run_id, meta.get("ticker") or state.get("company_of_interest"), snap["verdict"])
    meta_rows = "".join(f'<tr><th>{html_escape(k)}</th><td>{html_escape(v)}</td></tr>' for k, v in meta.items() if k not in {"decision"})
    body = f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html_escape(meta.get('ticker'))} — TradingAgents</title><style>{STYLE}</style></head><body><main><section class="hero"><div class="sigil">⚔️</div><div><h1>{html_escape(meta.get('ticker'))} / {html_escape(meta.get('date'))}</h1><p class="sub">Run {html_escape(run_id)} · <a href="/">Back to history</a></p></div></section><section class="detailgrid"><section><div class="card decision-hero tone-{html_escape(snap['tone'])}"><div class="verdict-box"><div class="verdict-label">Final decision</div><div class="verdict">{html_escape(snap['verdict'])}</div><div class="verdict-ticker">{html_escape(snap['headline'])}</div></div><div class="decision-summary"><h2>What this means</h2><p><strong>{html_escape(snap['explanation'])}</strong></p><p class="decision-actions">{html_escape(snap['action'])}</p><p class="tiny">Research-only. Not financial advice. The full agent report and raw state are below.</p><div class="btnrow"><a class="btn" href="/download/{html_escape(run_id)}.md">Download report</a><a class="btn secondary" href="/download/{html_escape(run_id)}.json">Download JSON</a><a class="btn secondary" href="/download/{html_escape(run_id)}.stdout.txt">Download stdout</a></div></div></div>{chart_panel}{resources_panel}<div class="card"><h2>Original final decision text</h2><div class="decision"><pre>{html_escape(final_decision or 'Not available')}</pre></div></div><div class="card"><div class="tabs"><button class="tab active" data-tab="report">Report</button><button class="tab" data-tab="state">State JSON</button><button class="tab" data-tab="stdout">Raw output</button></div><div id="report" class="section active"><div class="report">{html_escape(report)}</div></div><div id="state" class="section"><pre>{html_escape(state_pretty)}</pre></div><div id="stdout" class="section"><pre>{html_escape(stdout or 'No stdout recorded.')}</pre></div></div></section><aside class="card"><h2>Run metadata</h2><table class="table"><tbody>{meta_rows}</tbody></table></aside></section></main>''' + TAB_SCRIPT + CHART_SCRIPT + "</body></html>"
    return body.encode("utf-8")


def run_job(job_id: str, params: dict[str, str]) -> None:
    ticker = params["ticker"].upper()
    cmd = [
        str(PYTHON if PYTHON.exists() else sys.executable),
        str(RUNNER),
        ticker,
        params["date"],
        "--analysts",
        params["analysts"],
        "--model",
        params["model"],
    ]
    env = os.environ.copy()
    env.setdefault("OPENAI_API_KEY", "codex-proxy-noop")
    timeout = int(params.get("timeout", "1800"))
    proxy_metrics_before = fetch_proxy_metrics()
    started = time.time()
    initial_output = "$ " + " ".join(cmd) + "\n\n"
    stdout_path(job_id).write_text(initial_output)
    save_meta(job_id, {"status": "running", "started_at": now_iso(), "command": cmd})
    with JOBS_LOCK:
        JOBS[job_id].update({"status": "running", "output": initial_output})
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            with stdout_path(job_id).open("a") as fh:
                fh.write(line)
            with JOBS_LOCK:
                JOBS[job_id]["output"] = str(JOBS[job_id].get("output", "")) + line
            if time.time() - started > timeout:
                proc.kill()
                raise TimeoutError(f"Analysis exceeded {timeout} seconds")
        code = proc.wait(timeout=5)
        output = stdout_path(job_id).read_text(errors="replace")
        state_path = state_path_from_output(output)
        decision = extract_decision(output)
        proxy_metrics_after = fetch_proxy_metrics()
        meta = save_meta(
            job_id,
            {
                "status": "done" if code == 0 else "failed",
                "finished_at": now_iso(),
                "exit_code": code,
                "decision": decision,
                "state_path": state_path,
                "proxy_metrics_before": proxy_metrics_before,
                "proxy_metrics_after": proxy_metrics_after,
                "proxy_metrics_delta": metric_delta(proxy_metrics_before, proxy_metrics_after),
            },
        )
        report_path(job_id).write_text(generate_report(meta, load_state(meta), output))
        with JOBS_LOCK:
            JOBS[job_id].update({"status": meta["status"], "exit_code": code, "decision": decision, "state_path": state_path})
    except Exception as exc:  # noqa: BLE001 - surfaced to UI
        with stdout_path(job_id).open("a") as fh:
            fh.write(f"\nERROR: {exc}\n")
        output = stdout_path(job_id).read_text(errors="replace")
        proxy_metrics_after = fetch_proxy_metrics()
        meta = save_meta(job_id, {"status": "failed", "finished_at": now_iso(), "error": str(exc), "decision": extract_decision(output), "proxy_metrics_before": proxy_metrics_before, "proxy_metrics_after": proxy_metrics_after, "proxy_metrics_delta": metric_delta(proxy_metrics_before, proxy_metrics_after)})
        report_path(job_id).write_text(generate_report(meta, load_state(meta), output))
        with JOBS_LOCK:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["output"] = output
            JOBS[job_id]["error"] = str(exc)


class Handler(BaseHTTPRequestHandler):
    server_version = "TradingAgentsUI/0.2"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def send(self, code: int, content_type: str, body: bytes, filename: str = "") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, code: int, payload: object) -> None:
        self.send(code, "application/json", json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send(200, "text/html; charset=utf-8", page())
            return
        if parsed.path == "/health":
            self.json(200, {"status": "ok"})
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self.send(200, "text/html; charset=utf-8", page())
            return
        if path == "/health":
            self.json(200, {"status": "ok"})
            return
        if path == "/api/runs":
            self.json(200, list_runs())
            return
        if path.startswith("/api/chart/"):
            run_id = unquote(path.rsplit("/", 1)[-1])
            meta = load_meta(run_id)
            if not meta:
                self.json(404, {"error": "run not found"})
                return
            state = load_state(meta)
            final_decision = state.get("final_trade_decision") or meta.get("decision") or ""
            snap = decision_snapshot(final_decision, meta.get("ticker") or state.get("company_of_interest") or "")
            query = parse_qs(parsed.query)
            range_key = query.get("range", ["6m"])[-1]
            ticker = str(meta.get("ticker") or state.get("company_of_interest") or "").upper()
            if not TICKER_RE.match(ticker):
                self.json(400, {"error": "invalid ticker"})
                return
            self.json(200, get_chart_data(ticker, range_key, snap["verdict"]))
            return
        if path.startswith("/api/job/") or path.startswith("/api/run/"):
            run_id = unquote(path.rsplit("/", 1)[-1])
            meta = load_meta(run_id)
            if not meta:
                self.json(404, {"error": "run not found"})
                return
            output = stdout_path(run_id).read_text(errors="replace") if stdout_path(run_id).exists() else ""
            payload = dict(meta)
            payload["output"] = output
            self.json(200, payload)
            return
        if path.startswith("/run/"):
            run_id = unquote(path.rsplit("/", 1)[-1])
            body = detail_page(run_id)
            if not body:
                self.send(404, "text/plain", b"run not found")
                return
            self.send(200, "text/html; charset=utf-8", body)
            return
        if path.startswith("/download/"):
            name = unquote(path.rsplit("/", 1)[-1])
            for suffix, ctype, getter in [
                (".stdout.txt", "text/plain; charset=utf-8", lambda rid: stdout_path(rid).read_text(errors="replace") if stdout_path(rid).exists() else ""),
                (".json", "application/json", lambda rid: json.dumps(load_state(load_meta(rid) or {}) or load_meta(rid) or {}, indent=2, ensure_ascii=False)),
                (".md", "text/markdown; charset=utf-8", lambda rid: report_path(rid).read_text(errors="replace") if report_path(rid).exists() else generate_report(load_meta(rid) or {})),
            ]:
                if name.endswith(suffix):
                    run_id = name[: -len(suffix)]
                    if not load_meta(run_id):
                        self.send(404, "text/plain", b"run not found")
                        return
                    self.send(200, ctype, getter(run_id).encode("utf-8"), filename=name)
                    return
            self.send(404, "text/plain", b"download not found")
            return
        self.send(404, "text/plain", b"not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send(404, "text/plain", b"not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        data = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        params = {k: v[-1].strip() for k, v in data.items()}
        ticker = params.get("ticker", "").upper()
        run_date = params.get("date", "")
        analysts = [a for a in params.get("analysts", ",".join(ANALYSTS)).split(",") if a]
        model = params.get("model", "gpt-5.4-mini")
        if not TICKER_RE.match(ticker):
            self.json(400, {"error": "Invalid ticker"})
            return
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", run_date):
            self.json(400, {"error": "Invalid date"})
            return
        if any(a not in ANALYSTS for a in analysts):
            self.json(400, {"error": "Invalid analyst selection"})
            return
        if model not in MODELS:
            self.json(400, {"error": "Invalid model"})
            return
        job_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{ticker}-{uuid.uuid4().hex[:8]}"
        safe_params = {
            "ticker": ticker,
            "date": run_date,
            "analysts": ",".join(analysts) or ",".join(ANALYSTS),
            "model": model,
            "timeout": params.get("timeout", "1800"),
        }
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        meta = save_meta(job_id, {"status": "queued", **safe_params})
        stdout_path(job_id).write_text("Queued…\n")
        with JOBS_LOCK:
            JOBS[job_id] = {**meta, "output": "Queued…\n", "decision": ""}
        thread = threading.Thread(target=run_job, args=(job_id, safe_params), daemon=True)
        thread.start()
        self.json(202, {"id": job_id})


def main() -> int:
    parser = argparse.ArgumentParser(description="TradingAgents web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8505)
    args = parser.parse_args()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    discover_state_logs()
    reconcile_stale_jobs()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"TradingAgents UI listening on http://{args.host}:{args.port}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
