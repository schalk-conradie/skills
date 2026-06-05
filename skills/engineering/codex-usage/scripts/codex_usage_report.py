#!/usr/bin/env python3
"""Generate Codex usage and API-equivalent cost reports from local session logs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_TZ = timezone(timedelta(hours=2), "local")
PRICING_URL = "https://openai.com/api/pricing/"

# USD per 1M tokens. Refresh from official OpenAI pricing before relying on this
# for a final spend report.
FALLBACK_PRICES: dict[str, dict[str, float | None]] = {
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
    "gpt-5.2": {"input": 1.75, "cached_input": 0.175, "output": 14.00},
    "gpt-5.1": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5": {"input": 1.25, "cached_input": 0.125, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5-nano": {"input": 0.05, "cached_input": 0.005, "output": 0.40},
    "gpt-5-pro": {"input": 15.00, "cached_input": None, "output": 120.00},
}


@dataclass
class UsageEvent:
    ts: datetime
    model: str
    cost_model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int
    path: Path

    @property
    def uncached_input_tokens(self) -> int:
        return max(self.input_tokens - self.cached_input_tokens, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize local Codex token usage and API-equivalent costs.")
    parser.add_argument("--days", type=int, help="Number of days to include, including today.")
    parser.add_argument("--start", help="Start date, inclusive, as YYYY-MM-DD.")
    parser.add_argument("--end", help="End date, inclusive, as YYYY-MM-DD.")
    parser.add_argument("--assume-model", default="gpt-5.5", help="Model to use when logs do not contain a model.")
    parser.add_argument("--codex-home", default=str(Path.home() / ".codex"), help="Codex home directory.")
    parser.add_argument("--output-dir", help="Directory for Markdown and CSV reports.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown", help="Output format for stdout.")
    parser.add_argument("--no-fetch-pricing", action="store_true", help="Use embedded fallback pricing only.")
    return parser.parse_args()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    today = datetime.now(DEFAULT_TZ).date()
    if args.start:
        start_day = parse_date(args.start)
    elif args.days:
        start_day = today - timedelta(days=args.days - 1)
    else:
        start_day = today - timedelta(days=6)

    if args.end:
        end_day = parse_date(args.end)
    else:
        end_day = today

    if end_day < start_day:
        raise SystemExit("--end must be on or after --start")

    start_dt = datetime.combine(start_day, time.min, tzinfo=DEFAULT_TZ)
    end_dt = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=DEFAULT_TZ)
    return start_dt, end_dt


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(DEFAULT_TZ)


def candidate_session_files(codex_home: Path) -> list[Path]:
    paths: list[Path] = []
    for folder in (codex_home / "sessions", codex_home / "archived_sessions"):
        if folder.exists():
            paths.extend(folder.rglob("*.jsonl"))
    return paths


def detect_model(payload: dict[str, Any], obj: dict[str, Any]) -> str | None:
    info = payload.get("info") or {}
    for candidate in (
        info.get("model"),
        info.get("model_slug"),
        payload.get("model"),
        payload.get("model_slug"),
        obj.get("model"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def read_events(codex_home: Path, start: datetime, end: datetime, assume_model: str) -> list[UsageEvent]:
    events: list[UsageEvent] = []
    for path in candidate_session_files(codex_home):
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if '"token_count"' not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = obj.get("payload") or {}
                    if payload.get("type") != "token_count":
                        continue
                    ts = parse_timestamp(obj.get("timestamp"))
                    if ts is None or ts < start or ts >= end:
                        continue
                    usage = ((payload.get("info") or {}).get("last_token_usage") or {})
                    if not usage:
                        continue
                    model = detect_model(payload, obj) or "unknown"
                    cost_model = model if model != "unknown" else assume_model
                    input_tokens = int(usage.get("input_tokens") or 0)
                    cached = int(usage.get("cached_input_tokens") or 0)
                    output = int(usage.get("output_tokens") or 0)
                    reasoning = int(usage.get("reasoning_output_tokens") or 0)
                    total = int(usage.get("total_tokens") or (input_tokens + output))
                    events.append(
                        UsageEvent(
                            ts=ts,
                            model=model,
                            cost_model=cost_model,
                            input_tokens=input_tokens,
                            cached_input_tokens=cached,
                            output_tokens=output,
                            reasoning_output_tokens=reasoning,
                            total_tokens=total,
                            path=path,
                        )
                    )
        except OSError as exc:
            print(f"WARN: could not read {path}: {exc}", file=sys.stderr)
    return events


def fetch_pricing() -> tuple[dict[str, dict[str, float | None]], str]:
    prices = {k: dict(v) for k, v in FALLBACK_PRICES.items()}
    try:
        req = urllib.request.Request(PRICING_URL, headers={"User-Agent": "codex-usage-report/1.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return prices, f"fallback: could not fetch {PRICING_URL}: {exc}"

    text = re.sub(r"\s+", " ", html)
    for model in list(prices):
        pattern = re.compile(
            re.escape(model.upper().replace("-", " "))
            + r".{0,1200}?Input:\s*\$([0-9.]+).*?Cached input:\s*\$([0-9.]+|[-]).*?Output:\s*\$([0-9.]+)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            pattern = re.compile(
                re.escape(model)
                + r".{0,800}?\$([0-9.]+)\s*/\s*1M.*?\$([0-9.]+|[-])\s*/\s*1M.*?\$([0-9.]+)\s*/\s*1M",
                re.IGNORECASE,
            )
            match = pattern.search(text)
        if match:
            cached = None if match.group(2) == "-" else float(match.group(2))
            prices[model] = {"input": float(match.group(1)), "cached_input": cached, "output": float(match.group(3))}
    return prices, f"fetched: {PRICING_URL}"


def add_costs(row: dict[str, Any], prices: dict[str, dict[str, float | None]], model: str) -> None:
    price = prices.get(model)
    if price is None:
        price = FALLBACK_PRICES.get(model)
    if price is None:
        row["input_cost_usd"] = 0.0
        row["cached_input_cost_usd"] = 0.0
        row["output_cost_usd"] = 0.0
        row["total_cost_usd"] = 0.0
        row["pricing_missing"] = True
        return

    cached_rate = price["cached_input"] if price["cached_input"] is not None else price["input"]
    row["input_cost_usd"] = row["uncached_input_tokens"] / 1_000_000 * float(price["input"])
    row["cached_input_cost_usd"] = row["cached_input_tokens"] / 1_000_000 * float(cached_rate)
    row["output_cost_usd"] = row["output_tokens"] / 1_000_000 * float(price["output"])
    row["total_cost_usd"] = row["input_cost_usd"] + row["cached_input_cost_usd"] + row["output_cost_usd"]
    row["pricing_missing"] = False


def empty_row(label: str) -> dict[str, Any]:
    return {
        "date": label,
        "model": label,
        "requests": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "uncached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
        "input_cost_usd": 0.0,
        "cached_input_cost_usd": 0.0,
        "output_cost_usd": 0.0,
        "total_cost_usd": 0.0,
    }


def accumulate(row: dict[str, Any], event: UsageEvent) -> None:
    row["requests"] += 1
    row["input_tokens"] += event.input_tokens
    row["cached_input_tokens"] += event.cached_input_tokens
    row["uncached_input_tokens"] += event.uncached_input_tokens
    row["output_tokens"] += event.output_tokens
    row["reasoning_output_tokens"] += event.reasoning_output_tokens
    row["total_tokens"] += event.total_tokens


def aggregate(events: list[UsageEvent], start: datetime, end: datetime, prices: dict[str, dict[str, float | None]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    by_day: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}

    current = start.date()
    while current < end.date():
        label = current.isoformat()
        row = empty_row(label)
        row["date"] = label
        by_day[label] = row
        current += timedelta(days=1)

    for event in events:
        day = event.ts.date().isoformat()
        accumulate(by_day.setdefault(day, empty_row(day)), event)
        model_row = by_model.setdefault(event.cost_model, empty_row(event.cost_model))
        model_row["model"] = event.cost_model
        accumulate(model_row, event)

    for row in by_day.values():
        # Daily rows may contain mixed models; use per-event costs instead.
        row["input_cost_usd"] = 0.0
        row["cached_input_cost_usd"] = 0.0
        row["output_cost_usd"] = 0.0
        row["total_cost_usd"] = 0.0

    for event in events:
        cost_row = empty_row(event.cost_model)
        accumulate(cost_row, event)
        add_costs(cost_row, prices, event.cost_model)
        day_row = by_day[event.ts.date().isoformat()]
        day_row["input_cost_usd"] += cost_row["input_cost_usd"]
        day_row["cached_input_cost_usd"] += cost_row["cached_input_cost_usd"]
        day_row["output_cost_usd"] += cost_row["output_cost_usd"]
        day_row["total_cost_usd"] += cost_row["total_cost_usd"]

    for model, row in by_model.items():
        add_costs(row, prices, model)

    total = empty_row("TOTAL")
    for row in by_day.values():
        for key in ("requests", "input_tokens", "cached_input_tokens", "uncached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens"):
            total[key] += row[key]
        for key in ("input_cost_usd", "cached_input_cost_usd", "output_cost_usd", "total_cost_usd"):
            total[key] += row[key]

    return list(by_day.values()), list(by_model.values()), total


def money(value: float) -> str:
    return f"${value:,.2f}"


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: f"{row[key]:.6f}" if key.endswith("_usd") else row[key] for key in fields})


def markdown_table(rows: list[dict[str, Any]], label_key: str) -> str:
    lines = [f"| {label_key.title()} | Requests | Input | Cached | Fresh | Output | Total cost |", "|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(
            f"| {row[label_key]} | {row['requests']:,} | {row['input_tokens']:,} | {row['cached_input_tokens']:,} | "
            f"{row['uncached_input_tokens']:,} | {row['output_tokens']:,} | {money(row['total_cost_usd'])} |"
        )
    return "\n".join(lines)


def token_markdown_table(rows: list[dict[str, Any]], label_key: str) -> str:
    lines = [
        f"| {label_key.title()} | Requests | Input | Cached input | Fresh input | Output | Reasoning output | Total tokens |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row[label_key]} | {row['requests']:,} | {row['input_tokens']:,} | {row['cached_input_tokens']:,} | "
            f"{row['uncached_input_tokens']:,} | {row['output_tokens']:,} | {row['reasoning_output_tokens']:,} | {row['total_tokens']:,} |"
        )
    return "\n".join(lines)


def cost_markdown_table(rows: list[dict[str, Any]], label_key: str) -> str:
    lines = [
        f"| {label_key.title()} | Fresh input | Cached input | Output | Total |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row[label_key]} | {money(row['input_cost_usd'])} | {money(row['cached_input_cost_usd'])} | "
            f"{money(row['output_cost_usd'])} | **{money(row['total_cost_usd'])}** |"
        )
    return "\n".join(lines)


def render_markdown_report(daily: list[dict[str, Any]], models: list[dict[str, Any]], total: dict[str, Any], args: argparse.Namespace, pricing_source: str, over_272k: int) -> str:
    range_label = f"{daily[0]['date']} through {daily[-1]['date']}" if daily else "no rows"
    model_rows = sorted(models, key=lambda row: row["model"]) or [empty_row("none")]
    content = [
        "# Codex Usage Report",
        "",
        f"Estimated spend for **{range_label}**: **{money(total['total_cost_usd'])} USD**.",
        "",
        f"Pricing source: {pricing_source}.",
        f"Unknown model rows were costed as: **{args.assume_model}**.",
        f"Requests over 272K input tokens: **{over_272k}**.",
        "",
        "## Daily Token Breakdown",
        "",
        token_markdown_table(daily + [total], "date"),
        "",
        "## Daily Cost Breakdown",
        "",
        cost_markdown_table(daily + [total], "date"),
        "",
        "## Model Breakdown",
        "",
        token_markdown_table(model_rows, "model"),
        "",
        "## Model Cost Breakdown",
        "",
        cost_markdown_table(model_rows, "model"),
    ]
    return "\n".join(content) + "\n"


def write_markdown(path: Path, daily: list[dict[str, Any]], models: list[dict[str, Any]], total: dict[str, Any], args: argparse.Namespace, pricing_source: str, over_272k: int) -> None:
    path.write_text(render_markdown_report(daily, models, total, args, pricing_source, over_272k), encoding="utf-8")


def main() -> None:
    args = parse_args()
    start, end = resolve_range(args)
    prices, pricing_source = ({k: dict(v) for k, v in FALLBACK_PRICES.items()}, "embedded fallback") if args.no_fetch_pricing else fetch_pricing()
    events = read_events(Path(args.codex_home), start, end, args.assume_model)
    daily, models, total = aggregate(events, start, end, prices)
    over_272k = sum(1 for event in events if event.input_tokens > 272000)

    result = {
        "range": {"start": start.date().isoformat(), "end": (end.date() - timedelta(days=1)).isoformat()},
        "pricing_source": pricing_source,
        "assume_model": args.assume_model,
        "daily": daily,
        "models": models,
        "total": total,
        "requests_over_272k_input": over_272k,
    }

    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        start_label = start.date().isoformat()
        end_label = (end.date() - timedelta(days=1)).isoformat()
        daily_csv = output_dir / f"codex-usage-daily-{start_label}-to-{end_label}.csv"
        model_csv = output_dir / f"codex-usage-models-{start_label}-to-{end_label}.csv"
        markdown = output_dir / f"codex-usage-report-{start_label}-to-{end_label}.md"
        fields = [
            "date",
            "requests",
            "input_tokens",
            "cached_input_tokens",
            "uncached_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "total_tokens",
            "input_cost_usd",
            "cached_input_cost_usd",
            "output_cost_usd",
            "total_cost_usd",
        ]
        write_csv(daily_csv, daily + [total], fields)
        model_fields = fields.copy()
        model_fields[0] = "model"
        write_csv(model_csv, sorted(models, key=lambda row: row["model"]), model_fields)
        write_markdown(markdown, daily, models, total, args, pricing_source, over_272k)
        result["outputs"] = {"daily_csv": str(daily_csv), "model_csv": str(model_csv), "markdown": str(markdown)}

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_markdown_report(daily, models, total, args, pricing_source, over_272k))


if __name__ == "__main__":
    main()
