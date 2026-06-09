#!/usr/bin/env python3
"""Summarize local agent session cache evidence without printing transcript text.

The script reads Codex JSONL session logs, Claude aggregate stats, luce-bench
snapshots, and fizeau benchmark timing summaries when present. It intentionally
avoids emitting user, assistant, tool, or command content.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Usage:
    path: Path
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int

    @property
    def cache_ratio(self) -> float:
        if self.input_tokens <= 0:
            return 0.0
        return self.cached_input_tokens / self.input_tokens


@dataclass
class TurnTiming:
    path: Path
    duration_ms: float
    time_to_first_token_ms: float | None


@dataclass
class BenchTiming:
    path: Path
    prompt_tokens: int
    completion_tokens: int
    wall_seconds: float
    ttft_seconds: float | None
    decode_tokens_per_sec: float | None


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return ordered[idx]


def percentile_float(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return ordered[idx]


def usage_from_dict(path: Path, usage: dict[str, Any]) -> Usage | None:
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    cached = int(
        usage.get("cached_input_tokens")
        or usage.get("cached_tokens")
        or usage.get("prompt_tokens_details", {}).get("cached_tokens")
        or 0
    )
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    if input_tokens <= 0 and cached <= 0 and output_tokens <= 0:
        return None
    return Usage(path, input_tokens, cached, output_tokens, total_tokens)


def collect_codex_usage(path: Path) -> tuple[list[Usage], list[Usage], list[TurnTiming]]:
    last_turn: list[Usage] = []
    total: list[Usage] = []
    timings: list[TurnTiming] = []
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("type") == "task_complete":
                duration_ms = payload.get("duration_ms")
                if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
                    ttft_ms = payload.get("time_to_first_token_ms")
                    timings.append(
                        TurnTiming(
                            path=path,
                            duration_ms=float(duration_ms),
                            time_to_first_token_ms=(
                                float(ttft_ms)
                                if isinstance(ttft_ms, (int, float)) and ttft_ms >= 0
                                else None
                            ),
                        )
                    )
                continue
            if payload.get("type") != "token_count":
                continue
            info = payload.get("info")
            if not isinstance(info, dict):
                continue
            last = info.get("last_token_usage")
            if isinstance(last, dict):
                item = usage_from_dict(path, last)
                if item:
                    last_turn.append(item)
            aggregate = info.get("total_token_usage")
            if isinstance(aggregate, dict):
                item = usage_from_dict(path, aggregate)
                if item:
                    total.append(item)
    return last_turn, total, timings


def collect_claude_usage(path: Path) -> list[Usage]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return []

    found: list[Usage] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            item = usage_from_dict(path, value)
            if item:
                found.append(item)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return found


def summarize_usages(label: str, usages: list[Usage]) -> list[str]:
    if not usages:
        return [f"{label}: no token usage records found"]
    inputs = [u.input_tokens for u in usages]
    cached = [u.cached_input_tokens for u in usages]
    ratios = [u.cache_ratio for u in usages if u.input_tokens > 0]
    total_input = sum(inputs)
    total_cached = sum(cached)
    total_ratio = (total_cached / total_input) if total_input else 0.0
    return [
        f"{label}: {len(usages)} usage records",
        f"  input tokens: total={total_input:,} median={int(statistics.median(inputs)):,} p90={percentile(inputs, 0.90):,} max={max(inputs):,}",
        f"  cached input: total={total_cached:,} median={int(statistics.median(cached)):,} p90={percentile(cached, 0.90):,} max={max(cached):,}",
        f"  cache ratio: aggregate={pct(total_ratio)} median={pct(statistics.median(ratios))} p90={pct(percentile([round(r * 10000) for r in ratios], 0.90) / 10000)}",
    ]


def summarize_turn_timings(label: str, timings: list[TurnTiming]) -> list[str]:
    if not timings:
        return [f"{label}: no task timing records found"]
    durations = [t.duration_ms / 1000 for t in timings]
    ttfts = [
        t.time_to_first_token_ms / 1000
        for t in timings
        if t.time_to_first_token_ms is not None
    ]
    lines = [
        f"{label}: {len(timings)} task_complete records",
        "  wall/effective response seconds: "
        f"median={statistics.median(durations):.2f} "
        f"p90={percentile_float(durations, 0.90):.2f} "
        f"max={max(durations):.2f}",
    ]
    if ttfts:
        lines.append(
            "  time to first token seconds: "
            f"median={statistics.median(ttfts):.2f} "
            f"p90={percentile_float(ttfts, 0.90):.2f} "
            f"max={max(ttfts):.2f}"
        )
    return lines


def summarize_codex(codex_dir: Path, limit_files: int | None) -> list[str]:
    paths = sorted(codex_dir.rglob("*.jsonl"))
    if limit_files:
        paths = sorted(paths, key=lambda path: path.stat().st_mtime)[-limit_files:]

    turn_usages: list[Usage] = []
    final_totals: list[Usage] = []
    timings: list[TurnTiming] = []
    sessions_with_usage = 0

    for path in paths:
        turns, totals, task_timings = collect_codex_usage(path)
        if turns or totals:
            sessions_with_usage += 1
        turn_usages.extend(turns)
        timings.extend(task_timings)
        if totals:
            final_totals.append(totals[-1])

    lines = [
        f"codex: scanned {len(paths)} session files; {sessions_with_usage} had token_count records",
        *summarize_usages("codex per-turn last_token_usage", turn_usages),
        *summarize_usages("codex final per-session total_token_usage", final_totals),
        *summarize_turn_timings("codex task timing", timings),
    ]

    large_cached_turns = [
        u for u in turn_usages if u.input_tokens >= 50_000 and u.cache_ratio >= 0.80
    ]
    if large_cached_turns:
        lines.append(
            "codex large cached turns: "
            f"{len(large_cached_turns)} turns >=50k input tokens with >=80% cached"
        )
    return lines


def summarize_claude_stats(stats_path: Path) -> list[str]:
    if not stats_path.exists():
        return [f"claude stats: {stats_path} not found"]
    try:
        data = json.loads(stats_path.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return [f"claude stats: could not parse {stats_path}"]

    model_usage = data.get("modelUsage")
    if not isinstance(model_usage, dict):
        return [f"claude stats: no modelUsage records found in {stats_path}"]

    input_tokens = 0
    output_tokens = 0
    cache_read = 0
    cache_create = 0
    for usage in model_usage.values():
        if not isinstance(usage, dict):
            continue
        input_tokens += int(usage.get("inputTokens") or 0)
        output_tokens += int(usage.get("outputTokens") or 0)
        cache_read += int(usage.get("cacheReadInputTokens") or 0)
        cache_create += int(usage.get("cacheCreationInputTokens") or 0)

    cache_inclusive_input = input_tokens + cache_read + cache_create
    cache_read_ratio = cache_read / cache_inclusive_input if cache_inclusive_input else 0.0
    return [
        f"claude stats: {len(model_usage)} model usage records",
        f"  sessions={data.get('totalSessions'):,} messages={data.get('totalMessages'):,}",
        "  input volume: "
        f"uncached={input_tokens:,} cache_read={cache_read:,} "
        f"cache_creation={cache_create:,} output={output_tokens:,}",
        f"  cache-read share of cache-inclusive input={pct(cache_read_ratio)}",
    ]


def summarize_claude(claude_dir: Path) -> list[str]:
    session_paths = sorted((claude_dir / "sessions").glob("*.json"))
    history_path = claude_dir / "history.jsonl"
    usage: list[Usage] = []
    for path in session_paths:
        usage.extend(collect_claude_usage(path))

    history_lines = 0
    session_ids: set[str] = set()
    if history_path.exists():
        with history_path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                history_lines += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                session_id = row.get("sessionId")
                if isinstance(session_id, str):
                    session_ids.add(session_id)

    return [
        f"claude: scanned {len(session_paths)} session metadata files",
        f"claude history: {history_lines} entries across {len(session_ids)} session ids",
        *summarize_usages("claude session usage", usage),
        *summarize_claude_stats(claude_dir / "stats-cache.json"),
    ]


def collect_lucebench_snapshots(snapshots_dir: Path) -> list[BenchTiming]:
    rows: list[BenchTiming] = []
    if not snapshots_dir.exists():
        return rows
    for path in sorted(snapshots_dir.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, OSError):
            continue
        for row in data.get("rows") or []:
            if not isinstance(row, dict):
                continue
            wall = row.get("wall_seconds")
            prompt = row.get("prompt_tokens")
            completion = row.get("completion_tokens")
            if not isinstance(wall, (int, float)) or not isinstance(prompt, int):
                continue
            timings = row.get("timings") if isinstance(row.get("timings"), dict) else {}
            decode_tps = timings.get("decode_tokens_per_sec")
            rows.append(
                BenchTiming(
                    path=path,
                    prompt_tokens=prompt,
                    completion_tokens=completion if isinstance(completion, int) else 0,
                    wall_seconds=float(wall),
                    ttft_seconds=(
                        float(row["ttft_seconds"])
                        if isinstance(row.get("ttft_seconds"), (int, float))
                        else None
                    ),
                    decode_tokens_per_sec=(
                        float(decode_tps) if isinstance(decode_tps, (int, float)) else None
                    ),
                )
            )
    return rows


def summarize_bench_timings(label: str, rows: list[BenchTiming]) -> list[str]:
    if not rows:
        return [f"{label}: no benchmark timing rows found"]
    prompt_tokens = [row.prompt_tokens for row in rows]
    wall = [row.wall_seconds for row in rows]
    ttft = [row.ttft_seconds for row in rows if row.ttft_seconds is not None]
    decode_tps = [
        row.decode_tokens_per_sec
        for row in rows
        if row.decode_tokens_per_sec is not None
    ]
    lines = [
        f"{label}: {len(rows)} benchmark timing rows",
        f"  prompt tokens: median={int(statistics.median(prompt_tokens)):,} max={max(prompt_tokens):,}",
        "  wall seconds: "
        f"median={statistics.median(wall):.3f} "
        f"p90={percentile_float(wall, 0.90):.3f} max={max(wall):.3f}",
    ]
    if ttft:
        lines.append(
            "  ttft seconds: "
            f"median={statistics.median(ttft):.3f} "
            f"p90={percentile_float(ttft, 0.90):.3f} max={max(ttft):.3f}"
        )
    if decode_tps:
        lines.append(
            "  decode tokens/sec: "
            f"median={statistics.median(decode_tps):.1f} "
            f"p90={percentile_float(decode_tps, 0.90):.1f} "
            f"max={max(decode_tps):.1f}"
        )
    return lines


def summarize_lucebench(snapshots_dir: Path) -> list[str]:
    return summarize_bench_timings(
        f"luce-bench snapshots ({snapshots_dir})",
        collect_lucebench_snapshots(snapshots_dir),
    )


def summarize_fizeau_timing(timing_path: Path) -> list[str]:
    if not timing_path.exists():
        return [f"fizeau timing: {timing_path} not found"]
    try:
        data = json.loads(timing_path.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return [f"fizeau timing: could not parse {timing_path}"]
    if not isinstance(data, dict):
        return [f"fizeau timing: unexpected format in {timing_path}"]

    profiles = []
    bucket_rows = 0
    for profile, value in data.items():
        if not isinstance(value, dict):
            continue
        buckets = [b for b in value.get("buckets") or [] if isinstance(b, dict)]
        n_turns = int(value.get("n_turns") or 0)
        useful_buckets = [
            b
            for b in buckets
            if b.get("ttft_p50") is not None or b.get("decode_tps_p50") is not None
        ]
        bucket_rows += len(useful_buckets)
        if useful_buckets:
            profiles.append((profile, n_turns, useful_buckets))

    lines = [
        f"fizeau timing ({timing_path}): {len(profiles)} profiles with timing buckets",
        f"  bucket rows with ttft/decode data={bucket_rows}",
    ]
    for profile, n_turns, buckets in sorted(profiles, key=lambda item: item[1], reverse=True)[:8]:
        first = buckets[0]
        last = buckets[-1]
        lines.append(
            "  "
            f"{profile}: n_turns={n_turns:,}; "
            f"{first.get('label')} ttft_p50={first.get('ttft_p50')} "
            f"decode_tps_p50={first.get('decode_tps_p50')}; "
            f"{last.get('label')} ttft_p50={last.get('ttft_p50')} "
            f"decode_tps_p50={last.get('decode_tps_p50')}"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-dir", type=Path, default=Path.home() / ".codex" / "sessions")
    parser.add_argument("--claude-dir", type=Path, default=Path.home() / ".claude")
    parser.add_argument("--lucebench-snapshots-dir", type=Path, default=Path("snapshots"))
    parser.add_argument(
        "--fizeau-timing",
        type=Path,
        default=Path("/Users/erik/Projects/fizeau-docker-attempt-image/docs/benchmarks/data/timing.json"),
    )
    parser.add_argument(
        "--codex-limit-files",
        type=int,
        default=None,
        help="Only scan the newest N Codex session files.",
    )
    args = parser.parse_args()

    for line in summarize_codex(args.codex_dir, args.codex_limit_files):
        print(line)
    print()
    for line in summarize_claude(args.claude_dir):
        print(line)
    print()
    for line in summarize_lucebench(args.lucebench_snapshots_dir):
        print(line)
    print()
    for line in summarize_fizeau_timing(args.fizeau_timing):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
