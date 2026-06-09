#!/usr/bin/env python3
"""Aggregate Fizeau session timing by context length and model overlap.

The script scans captured Fizeau JSONL session logs and reads only structured
LLM response metadata. It does not print prompts, completions, tool arguments,
or other transcript content.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROOT = Path("/Users/erik/Projects/fizeau")
BUCKETS = [
    ("0-10k", 0, 10_000),
    ("10-30k", 10_000, 30_000),
    ("30-60k", 30_000, 60_000),
    ("60-120k", 60_000, 120_000),
    ("120k+", 120_000, 10_000_000),
]


@dataclass(frozen=True)
class TurnTiming:
    path: Path
    task: str | None
    provider: str
    is_openrouter: bool
    model: str
    input_tokens: int
    completion_tokens: int
    ttft_seconds: float
    decode_tps: float | None
    latency_seconds: float | None

    @property
    def bucket(self) -> str:
        for label, lo, hi in BUCKETS:
            if lo <= self.input_tokens < hi:
                return label
        return "overflow"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return ordered[idx]


def parse_ts(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        head, tail = text.split(".", 1)
        if "+" in tail:
            frac, offset = tail.split("+", 1)
            text = f"{head}.{frac[:6].ljust(6, '0')}+{offset}"
        elif "-" in tail:
            frac, offset = tail.split("-", 1)
            text = f"{head}.{frac[:6].ljust(6, '0')}-{offset}"
        else:
            text = f"{head}.{tail[:6].ljust(6, '0')}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def session_paths(root: Path, include_all: bool) -> list[Path]:
    candidates: set[Path] = set()
    for path in (root / "benchmark-results").rglob("agent/sessions/*.jsonl"):
        if "/verify-worktree/" not in str(path):
            candidates.add(path)
    for path in (root / "bench" / "results").rglob("agent/sessions/*.jsonl"):
        if "/verify-worktree/" not in str(path):
            candidates.add(path)
    for path in (root / ".fizeau" / "sessions").glob("*.jsonl"):
        candidates.add(path)
    if include_all:
        for path in root.rglob("*.jsonl"):
            if "/verify-worktree/" not in str(path):
                candidates.add(path)
    return sorted(candidates)


def openrouter_provider(attempt: dict[str, Any], path: Path) -> bool:
    provider_name = str(attempt.get("provider_name") or "").lower()
    provider_system = str(attempt.get("provider_system") or "").lower()
    server = str(attempt.get("server_address") or "").lower()
    path_text = str(path).lower()
    return (
        provider_name == "openrouter"
        or provider_system == "openrouter"
        or "openrouter" in server
        or "openrouter" in path_text
    )


def openrouter_turn(turn: TurnTiming) -> bool:
    return turn.is_openrouter


def task_from_path(path: Path) -> str | None:
    parts = path.parts
    if "terminal-bench-2-1" not in parts:
        return None
    idx = parts.index("terminal-bench-2-1")
    if idx + 1 >= len(parts):
        return None
    return parts[idx + 1]


def provider_name(attempt: dict[str, Any], path: Path) -> str:
    provider = str(
        attempt.get("provider_name")
        or attempt.get("provider_system")
        or "unknown"
    )
    if provider == "unknown" and "openrouter" in str(path).lower():
        return "openrouter"
    return provider


def collect_turns(path: Path) -> list[TurnTiming]:
    turns: list[TurnTiming] = []
    task = task_from_path(path)
    request_ts: float | None = None
    first_delta_ts: float | None = None
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            row_type = row.get("type")
            row_ts = parse_ts(row.get("ts"))
            if row_type == "llm.request":
                request_ts = row_ts
                first_delta_ts = None
                continue
            if row_type == "llm.delta" and request_ts is not None and first_delta_ts is None:
                first_delta_ts = row_ts
                continue
            if row_type != "llm.response":
                continue
            data = row.get("data")
            if not isinstance(data, dict):
                continue
            attempt = data.get("attempt")
            if not isinstance(attempt, dict):
                continue
            is_openrouter = openrouter_provider(attempt, path)
            usage = data.get("usage")
            timing = attempt.get("timing")
            if not isinstance(usage, dict) or not isinstance(timing, dict):
                continue
            input_tokens = usage.get("input")
            output_tokens = usage.get("output")
            if not isinstance(output_tokens, int):
                total_tokens = usage.get("total")
                output_tokens = (
                    max(0, total_tokens - input_tokens)
                    if isinstance(total_tokens, int) and isinstance(input_tokens, int)
                    else 0
                )
            if not isinstance(input_tokens, int) or input_tokens <= 0:
                continue
            ttft_seconds = None
            if request_ts is not None and first_delta_ts is not None and first_delta_ts > request_ts:
                ttft_seconds = first_delta_ts - request_ts
            else:
                first_token_ns = timing.get("first_token")
                if isinstance(first_token_ns, (int, float)) and first_token_ns > 0:
                    ttft_seconds = first_token_ns / 1_000_000_000
            if ttft_seconds is None:
                continue
            decode_tps = None
            if output_tokens > 0 and first_delta_ts is not None and row_ts is not None and row_ts > first_delta_ts:
                decode_tps = output_tokens / (row_ts - first_delta_ts)
            latency_ms = data.get("latency_ms")
            model = str(data.get("model") or attempt.get("response_model") or "unknown")
            turns.append(
                TurnTiming(
                    path=path,
                    task=task,
                    provider=provider_name(attempt, path),
                    is_openrouter=is_openrouter,
                    model=model,
                    input_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    ttft_seconds=ttft_seconds,
                    decode_tps=decode_tps,
                    latency_seconds=(
                        float(latency_ms) / 1000
                        if isinstance(latency_ms, (int, float))
                        else None
                    ),
                )
            )
            request_ts = None
            first_delta_ts = None
    return turns


def fmt(value: float | None, precision: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{precision}f}"


def summarize_group(label: str, turns: list[TurnTiming]) -> list[str]:
    lines: list[str] = []
    lines.append(f"{label}: {len(turns):,} turns")
    by_bucket: dict[str, list[TurnTiming]] = defaultdict(list)
    for turn in turns:
        by_bucket[turn.bucket].append(turn)

    lines.append("| context bucket | turns | input median | ttft p50 | ttft p90 | decode rows | decode tps p50 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for bucket, _, _ in BUCKETS:
        rows = by_bucket.get(bucket, [])
        if not rows:
            lines.append(f"| {bucket} | 0 | - | - | - | - | - |")
            continue
        inputs = [float(row.input_tokens) for row in rows]
        ttfts = [row.ttft_seconds for row in rows]
        decode = [row.decode_tps for row in rows if row.decode_tps is not None]
        lines.append(
            f"| {bucket} | {len(rows):,} | {int(statistics.median(inputs)):,} | "
            f"{fmt(statistics.median(ttfts))} | {fmt(percentile(ttfts, 0.90))} | "
            f"{len(decode):,} | {fmt(statistics.median(decode), 1) if decode else '-'} |"
        )
    return lines


def summarize_models(turns: list[TurnTiming], top_n: int) -> list[str]:
    lines: list[str] = []
    model_counts = Counter(turn.model for turn in turns)
    for model, count in model_counts.most_common(top_n):
        model_turns = [turn for turn in turns if turn.model == model]
        lines.append("")
        lines.extend(summarize_group(f"model {model}", model_turns))
    return lines


def model_matches(turn: TurnTiming, pattern: str) -> bool:
    haystack = f"{turn.model} {turn.provider}".lower()
    return pattern.lower() in haystack


def task_set(turns: list[TurnTiming], pattern: str) -> set[str]:
    return {turn.task for turn in turns if turn.task and model_matches(turn, pattern)}


def summarize_common_tasks(
    turns: list[TurnTiming],
    baseline_pattern: str,
    compare_patterns: list[str],
) -> list[str]:
    lines: list[str] = []
    baseline_tasks = task_set(turns, baseline_pattern)
    lines.append("")
    lines.append("Apples-to-apples task overlap")
    lines.append(
        f"baseline `{baseline_pattern}`: {len(baseline_tasks)} terminal-bench tasks with timing"
    )
    for pattern in compare_patterns:
        candidate_tasks = task_set(turns, pattern)
        common = sorted(baseline_tasks & candidate_tasks)
        lines.append(
            f"`{pattern}`: {len(candidate_tasks)} tasks; overlap with baseline={len(common)}"
        )
        if not common:
            continue
        baseline_turns = [
            turn
            for turn in turns
            if turn.task in common and model_matches(turn, baseline_pattern)
        ]
        candidate_turns = [
            turn
            for turn in turns
            if turn.task in common and model_matches(turn, pattern)
        ]
        lines.append("")
        lines.extend(summarize_group(f"paired baseline {baseline_pattern} vs {pattern}", baseline_turns))
        lines.append("")
        lines.extend(summarize_group(f"paired comparator {pattern}", candidate_turns))
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--include-all-jsonl",
        action="store_true",
        help="Scan all JSONL under root, not only captured agent/sessions logs.",
    )
    parser.add_argument("--top-models", type=int, default=4)
    parser.add_argument(
        "--baseline-model",
        default="qwen/qwen3.6-27b-20260422",
        help="Substring used as the baseline model for task-overlap comparisons.",
    )
    parser.add_argument(
        "--compare-model",
        action="append",
        default=None,
        help="Substring for a comparator model. Can be supplied more than once.",
    )
    args = parser.parse_args()
    if args.compare_model is None:
        args.compare_model = [
            "anthropic/claude-4.6-sonnet",
            "openai/gpt-5.4-mini",
            "gpt-5.5",
        ]

    paths = session_paths(args.root, args.include_all_jsonl)
    turns: list[TurnTiming] = []
    for path in paths:
        turns.extend(collect_turns(path))
    openrouter_turns = [turn for turn in turns if openrouter_turn(turn)]

    print(f"scanned session files: {len(paths):,}")
    print()
    for line in summarize_group("all OpenRouter", openrouter_turns):
        print(line)
    for line in summarize_models(openrouter_turns, args.top_models):
        print(line)
    for line in summarize_common_tasks(turns, args.baseline_model, args.compare_model):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
