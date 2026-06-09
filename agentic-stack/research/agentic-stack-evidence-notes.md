# Agentic stack evidence notes

Working notes for revising
`The agentic stack is the product, not the model.md`.

## Current thesis

A useful coding agent is an integrated stack, not a model alone. The inference
engine matters because multi-turn agent loops repeatedly resend a growing
conversation. If the engine can reuse the shared prefix, the loop stays
responsive. If it cannot, each turn pays the full long-context prefill cost
again.

The open-weights version of the argument is narrower. We do not own model RL, so
we cannot train the model into our exact tool protocol. We do own the inference
engine, the harness, the evals, model metadata, `/props`, and autotuning. Those
layers are where a local stack can close part of the gap.

## Proposed revised outline

1. **Start as an independent investigation, not a lucebox pitch**
   - Opening frame: local models are having a moment. Public benchmark posts and
     local-inference leaderboards routinely show impressive tokens/sec on
     3090-class rigs, 5090-class rigs, Apple Silicon, and local AI workstations
     like DGX Spark.
   - Concede the point: local models are good, and local decode throughput can
     be excellent on the right hardware.
   - Investigation question: do those numbers predict what happens in real
     agentic coding work, where every turn resends a long, growing context?

2. **The model-only story breaks down in agent loops**
   - A coding agent is not a model call, it is a repeated loop over context,
     tools, verification, and serving.
   - Define the stack briefly: context, guardrails, implementation,
     self-discovery, harness, inference engine, model.
   - Claim: in a long multi-turn loop, the inference engine becomes a product
     layer because every turn resends a mostly shared prefix.

3. **Short-prompt throughput is not the agent workload**
   - Use public local-inference benchmark examples to show the common frame:
     7B/13B models, Q4 quantization, single-stream decode, short or moderate
     prompts, tokens/sec as the headline metric.
   - Identify the "write a story" pattern explicitly: a tiny or synthetic prompt
     asks the model to produce hundreds or thousands of tokens, then the result
     reports output tokens/sec. That is a valid decode benchmark, but it mostly
     removes the hard parts of agent serving.
   - Contrast that with agent loops: large static system/tool context,
     accumulated assistant/tool history, repeated requests, long prefill, cache
     hit/miss behavior, and time to first token.
   - Core distinction: decode tokens/sec answers "how fast can the model keep
     talking once it starts?" Agentic responsiveness asks "how long until the
     next useful turn starts after resending the session?"

4. **Public docs say the cache is part of the product**
   - Use OpenAI and Anthropic prompt-caching docs to establish the mechanism:
     repeated prefixes, stable system/tool content, latency and cost reduction,
     cached-token counters.
   - Use Anthropic tool-use guidance to connect cacheability to agent harness
     design: system prompts and core tool definitions should stay stable.
   - Use Codex public material for the broader vertical-integration point:
     model training, harness behavior, and test-running loops are designed
     together.

5. **Our local agent traces show why this matters**
   - Codex sessions: recent 200-session slice has 97,109-token median input and
     99.0% median cached-input ratio; full corpus has about 105k median input
     and 99.2% median cached-input ratio.
   - Claude stats: 68.4B cache-read input tokens and 97.2% cache-read share of
     cache-inclusive input.
   - Interpretation: these agents are not getting fast by sending short prompts;
     they are staying usable while moving huge prompts through cache-heavy
     serving stacks.

6. **Fizeau shows the timing curve when context grows**
   - OpenRouter terminal-bench corpus: 7,247 turns; TTFT rises from 0.86s at
     0-10k input tokens to 3.26s at 60-120k.
   - Dominant Qwen OpenRouter model: 0.80s to 4.15s TTFT from 0-10k to
     60-120k, with decode drifting down from 50.2 to 41.7 tps.
   - This is the context-depth evidence: even a hosted inference path pays more
     as the prompt gets deeper.

7. **Provider/runtime differences are large, not cosmetic**
   - GPT-5.5 paired by terminal-bench task id: 23 overlapping tasks, 1,384 turns;
     TTFT stays around 1.0-1.3s through 60k+ context and decode is much higher
     than the Qwen OpenRouter baseline.
   - Claude Sonnet and OpenRouter GPT-5 mini overlap is only 5 tasks each, so use
     those as sanity checks, not as the main claim.
   - Local-provider overlap is broad and strong: vLLM, OMLX, llama-server, and
     DS4 each overlap the OpenRouter Qwen baseline on roughly 76-82 tasks.
   - Their TTFT/decode profiles differ dramatically, which supports the claim
     that serving path, cache behavior, quantization, batching, and streaming are
     product variables.

8. **What this does and does not prove**
   - Proves: real agent loops use huge cache-backed inputs; context depth affects
     latency; inference stacks differ materially across providers and local
     servers.
   - Does not yet prove: a clean cache-on/cache-off latency delta for the exact
     same replayed prompts.
   - Name the gold-standard follow-up: run `agentic-session` with prefix reuse
     on/off and plot prompt tokens, reused prefix tokens, first-content/TTFT,
     wall time, and decode rate by turn.

9. **Where lucebox fits**
   - We cannot reproduce closed-vendor model RL or train the exact tool protocol
     into downloaded weights.
   - We can own the inference engine, harness contract, model cards, `/props`,
     cache settings, autotuning, evals, and agentic-session replay.
   - Conclusion: the local stack competes by integrating the layers it controls.
     The model is important, but it is not the product.

## Repo evidence already available

- `Multi-turn agentic loops as a benchmark target` gives the core prompt shape:
  each turn carries the full prior history, and turn N is turn N-1 plus a suffix.
  It also states the measurement gap: the `agentic-session` suite exists, but no
  captured `agentic-session` baseline has landed yet.
- The same post has single-turn agent evidence: Gemma 4 26B is 75% on local
  `agent` probes, but 0/30 on local forge tool-calling because of protocol and
  budget mismatch. The same model is 83-87% on OpenRouter forge scenarios.
- `Gemma 4 26B across serving paths` shows identical weights moving by serving
  path: accuracy shifts by about 5 points and throughput by about 3x.
- `Tuning Qwen3.6-27B decode on a 3090 Ti` shows engine knobs moving throughput:
  DFlash on/off is about 2.5x, KV cache type changes decode rate, and context /
  PFlash choices affect VRAM headroom.
- `/props`, model cards, and autotune support the contract argument: the harness
  can discover runtime context limits, cache settings, model card source,
  sampling defaults, and budget envelopes instead of guessing.

## Public support

- Representative local-throughput framing:
  - LocalMaxxing is useful because it is a public local-inference benchmark site
    with machine-readable fields for output tok/s, prefill tok/s, total tok/s,
    TTFT, VRAM, prompt tokens, output tokens, context length, model, hardware,
    and engine. Source: `https://www.localmaxxing.com/en` and
    `https://www.localmaxxing.com/en/api-docs`.
  - LocalMaxxing also shows the benchmark-shape problem directly. Example RTX
    5090 runs include 25 prompt tokens -> 256 output tokens at 228.56 tok/s,
    200 prompt tokens -> 4096 output tokens at 141.9 tok/s, and 514 prompt
    tokens -> 1024 output tokens at 240.9 tok/s. Example RTX 3090 runs include
    52 prompt tokens -> 1000 output tokens at 52.7 tok/s. These are decode-heavy
    tests, close to the "write a story" shape, not agentic traces.
  - LocalMaxxing does have more relevant long-prompt single-request examples too,
    such as RTX 3090 runs with 39,777 prompt tokens and 100,000 prompt tokens,
    and RTX PRO 6000 Blackwell runs at 32k/66k context. Those are useful for
    prefill and TTFT, but they still do not test repeated multi-turn cache reuse.
  - Presenc AI's 2026 local LLM benchmark says tokens/sec is the headline number
    for interactivity and reports roughly 130-150 tps for 7B Q4 on RTX 5090,
    95-110 tps on Mac Studio M5 Max, and 105-125 tps on DGX Spark. It also
    notes that prompt processing/prefill is the bottleneck for agent-style
    workloads. Source:
    `https://presenc.ai/research/local-llm-tokens-per-second-benchmarks-2026`.
  - Hardware Corner's RTX 3090 page frames the 3090 as still viable for local LLM
    work and reports high prompt-processing numbers for smaller Qwen models, but
    also notes that generation speed can drop to single-digit tokens/sec when
    large models require offload. Source:
    `https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-3090/`.
  - OpenClaw's RTX 3090 local-LLM guide gives a more workload-adjacent 24GB
    example: Qwen 3.6 27B Q4 at roughly 35 tokens/sec on a 3090-class card.
    Source: `https://openclawdc.com/blog/best-local-llm-rtx-3090/`.
  - A 2026 Apple Silicon local-runtime study compares MLX, MLC-LLM, Ollama,
    llama.cpp, and PyTorch MPS across prompts up to 100k tokens and explicitly
    measures TTFT, throughput, long-context behavior, KV/prompt caching,
    streaming, batching, and deployment complexity. That supports our claim that
    runtime behavior is workload-specific rather than reducible to one tps
    number. Source: `https://arxiv.org/abs/2511.05502`.
- OpenAI prompt caching docs say cache hits depend on repeated prefixes, that
  static content should come first, and that messages plus tools can be cached.
  They also expose `cached_tokens` in usage.
- Anthropic prompt caching docs frame caching as useful for conversational
  agents, coding assistants, and repeated long-context calls, with latency and
  cost reductions for long prompts.
- Anthropic advanced tool-use writing explicitly calls out keeping system prompts
  and core tool definitions cacheable.
- vLLM's automatic prefix caching docs say shared-prefix KV blocks can be reused
  rather than recomputed. That shows the same mechanism exists in local/open
  serving stacks, but our measurements suggest having the feature in a runtime
  is not the same as having an agent stack tuned around it.
- OpenAI's Codex system card says codex-1 was trained with reinforcement
  learning on real-world coding tasks and learns to run tests until passing
  results are achieved. That supports the model-plus-harness training claim for
  Codex, but not every closed vendor.

## Benchmark-shape taxonomy for the post

This framing helps avoid overclaiming. We should not say local throughput
benchmarks are wrong. We should say they answer a different question.

| Shape | Examples | What it measures | Why it is not agentic |
| --- | --- | --- | --- |
| Decode demo / "write a story" | LocalMaxxing short-prompt runs; many Ollama, LM Studio, llama.cpp screenshots; "tell me a story" tests | Output tok/s after the model is already generating | Tiny prompt, no tools, no growing history, no repeated prefix, little cache pressure |
| Synthetic throughput bench | `llama-bench`, `llama-batched-bench`, vLLM offline throughput, batch sweeps | Hardware/runtime throughput capacity | Often offline or batched; optimizes aggregate tok/s rather than one agent turn's TTFT/wall time |
| Long-prompt single request | LocalMaxxing 32k/64k/100k prompt runs; Apple Silicon runtime study; long-context prefill tests | Prefill speed, TTFT, context fit, KV memory pressure | Useful but still one request; it does not measure cache reuse across turns |
| Single-turn quality eval | MMLU, GPQA, AIME, HumanEval, ds4-eval, one-shot code/agent probes | Model/task quality under fixed prompt shape | No session growth, no tool-result accumulation, no per-turn latency compounding |
| Agentic task benchmark | Terminal-Bench, SWE-bench with agent harnesses, Fizeau terminal-bench logs, planned `agentic-session` replay | Whole loop: context management, tools, harness, serving stack, model | This is the relevant shape for the blog's inference-stack claim |

The line for the post: a 200 tok/s local decode result can be true and still be
irrelevant to whether a local coding agent feels fast. The agent workload is
prompt-heavy, prefix-reuse-heavy, and latency-sensitive at every turn.

## Local session-cache evidence

I added `scripts/analyze_agent_session_cache.py` to summarize local session
usage without printing transcript content.

Commands:

```bash
python3 scripts/analyze_agent_session_cache.py --codex-limit-files 20
python3 scripts/analyze_agent_session_cache.py --codex-limit-files 200
python3 scripts/analyze_agent_session_cache.py
```

I also added `scripts/analyze_fizeau_openrouter_timing.py` to summarize Fizeau
OpenRouter terminal-bench session timings by context bucket. It scans captured
`agent/sessions/*.jsonl` logs and reads only structured `llm.request`,
`llm.delta`, and `llm.response` metadata. It computes TTFT as first
`llm.delta.ts - llm.request.ts`, decode tokens/sec as
`usage.output / (llm.response.ts - first llm.delta.ts)`, and context depth as
`usage.input`.

Full local Codex corpus result after adding task timing:

```text
codex: scanned 15068 session files; 4672 had token_count records
codex per-turn last_token_usage: 222825 usage records
  input tokens: total=24,740,431,389 median=105,524 p90=195,857 max=257,483
  cached input: total=23,867,755,136 median=102,272 p90=193,408 max=244,608
  cache ratio: aggregate=96.5% median=99.2% p90=99.8%
codex final per-session total_token_usage: 4672 usage records
  input tokens: total=21,161,979,415 median=568,734 p90=9,305,824 max=852,293,402
  cached input: total=20,425,354,624 median=508,032 p90=9,104,384 max=832,471,040
  cache ratio: aggregate=96.5% median=91.3% p90=97.8%
codex task timing: 15420 task_complete records
  wall/effective response seconds: median=3.70 p90=198.64 max=81552.39
  time to first token seconds: median=5.65 p90=12.10 max=125.31
codex large cached turns: 178833 turns >=50k input tokens with >=80% cached
```

Newest 200 Codex sessions:

```text
codex: scanned 200 session files; 73 had token_count records
codex per-turn last_token_usage: 2452 usage records
  input tokens: total=266,653,221 median=97,109 p90=194,460 max=241,022
  cached input: total=255,075,840 median=93,568 p90=191,360 max=239,488
  cache ratio: aggregate=95.7% median=99.0% p90=99.8%
codex final per-session total_token_usage: 73 usage records
  input tokens: total=266,653,221 median=659,525 p90=9,891,743 max=43,117,740
  cached input: total=255,075,840 median=601,728 p90=9,337,984 max=41,060,096
  cache ratio: aggregate=95.7% median=90.6% p90=97.7%
codex task timing: 257 task_complete records
  wall/effective response seconds: median=9.11 p90=314.72 max=3264.49
  time to first token seconds: median=6.86 p90=11.71 max=125.31
codex large cached turns: 1993 turns >=50k input tokens with >=80% cached
```

Newest 20 Codex sessions:

```text
codex: scanned 20 session files; 11 had token_count records
codex per-turn last_token_usage: 744 usage records
  input tokens: total=90,862,500 median=106,254 p90=210,457 max=238,825
  cached input: total=86,219,264 median=104,064 p90=206,208 max=237,952
  cache ratio: aggregate=94.9% median=99.0% p90=99.8%
codex final per-session total_token_usage: 11 usage records
  input tokens: total=90,862,500 median=5,192,650 p90=16,346,718 max=35,346,071
  cached input: total=86,219,264 median=4,768,000 p90=15,486,336 max=33,583,360
  cache ratio: aggregate=94.9% median=95.0% p90=97.5%
codex task timing: 57 task_complete records
  wall/effective response seconds: median=66.84 p90=268.11 max=891.85
  time to first token seconds: median=6.41 p90=12.26 max=17.30
codex large cached turns: 608 turns >=50k input tokens with >=80% cached
```

Claude local result:

```text
claude: scanned 6 session metadata files
claude history: 15378 entries across 6746 session ids
claude session usage: no token usage records found
claude stats: 7 model usage records
  sessions=9,512 messages=944,610
  input volume: uncached=17,262,117 cache_read=68,412,289,694 cache_creation=1,922,747,203 output=302,677,826
  cache-read share of cache-inclusive input=97.2%
```

Interpretation:

- Codex sessions are direct local evidence that agent turns are enormous and
  heavily cache-backed. Median per-turn input is about 105k tokens across the
  full corpus, with a 99.2% median cached-input ratio.
- The strongest blog-safe number is probably the recent 200-session slice: it is
  large enough to avoid cherry-picking and smaller than the full historical
  corpus, with a 97,109-token median input and 99.0% median cache ratio.
- Claude on this machine does not expose comparable per-session counters in
  `~/.claude/sessions`; those files are session metadata, while `history.jsonl`
  only has display/history entries. It does expose aggregate cache counters in
  `~/.claude/stats-cache.json`: 68.4B cache-read input tokens, 1.9B cache
  creation tokens, and a 97.2% cache-read share of cache-inclusive input.
- Codex `task_complete.duration_ms` is effective turn time, not pure model
  inference time. It includes agent/tool work. `time_to_first_token_ms` is closer
  to model-facing latency, but still comes from an agent client trace.

## Local timing evidence

The current repo's luce-bench smoke snapshots expose row-level wall time, TTFT,
prompt tokens, completion tokens, and decode tokens/sec. They are tiny smoke
runs, useful for schema and methodology rather than a strong blog claim:

```text
luce-bench snapshots (snapshots): 6 benchmark timing rows
  prompt tokens: median=50 max=53
  wall seconds: median=1.387 p90=3.697 max=17.359
  ttft seconds: median=0.588 p90=1.457 max=12.841
  decode tokens/sec: median=13.1 p90=19.5 max=36.2
```

The useful context-depth timing evidence is in the fizeau benchmark data at
`/Users/erik/Projects/fizeau/docs/benchmarks/data/timing.json`.
It has 14 profiles with timing buckets and 41 bucket rows with TTFT/decode data.
Representative profiles:

```text
fiz-openrouter-qwen3-6-27b: n_turns=6,357
  0-10k: ttft_p50=0.805s decode_tps_p50=49.9
  60-120k: ttft_p50=2.477s decode_tps_p50=43.9

fiz-openai-gpt-5-5: n_turns=2,582
  0-10k: ttft_p50=0.365s decode_tps_p50=382.7
  60-120k: ttft_p50=1.342s decode_tps_p50=179.5

vidar-qwen3-6-27b: n_turns=2,344
  0-10k: ttft_p50=9.859s decode_tps_p50=16.3
  60-120k: ttft_p50=23.335s decode_tps_p50=11.2

sindri-club-3090-llamacpp: n_turns=1,567
  0-10k: ttft_p50=1.992s decode_tps_p50=22.9
  120k+: ttft_p50=4.128s decode_tps_p50=9.3

vidar-ds4: n_turns=1,245
  0-10k: ttft_p50=16.497s decode_tps_p50=24.5
  120k+: ttft_p50=69.886s decode_tps_p50=18.6
```

This supports the context-depth part of the post directly: as prompt/context
depth moves from short to long buckets, first-token latency rises and decode
tokens/sec often falls. It does not isolate cache on/off by itself.

The strongest OpenRouter-specific evidence comes from the terminal-bench session
logs in `/Users/erik/Projects/fizeau`. Raw scan:

```bash
python3 scripts/analyze_fizeau_openrouter_timing.py
```

Result:

```text
scanned session files: 1,735

all OpenRouter: 7,247 OpenRouter turns
| context bucket | turns | input median | ttft p50 | ttft p90 | decode rows | decode tps p50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0-10k | 4,008 | 5,119 | 0.86 | 2.72 | 4,008 | 54.5 |
| 10-30k | 2,419 | 16,762 | 1.11 | 4.12 | 2,419 | 52.0 |
| 30-60k | 699 | 38,250 | 2.03 | 5.78 | 699 | 49.2 |
| 60-120k | 121 | 72,624 | 3.26 | 10.11 | 121 | 43.1 |
| 120k+ | 0 | - | - | - | - | - |
```

For the dominant OpenRouter model in this scan:

```text
model qwen/qwen3.6-27b-20260422: 6,323 OpenRouter turns
| context bucket | turns | input median | ttft p50 | ttft p90 | decode rows | decode tps p50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0-10k | 3,307 | 5,313 | 0.80 | 2.81 | 3,307 | 50.2 |
| 10-30k | 2,296 | 16,858 | 1.11 | 4.25 | 2,296 | 51.2 |
| 30-60k | 611 | 39,082 | 1.67 | 5.95 | 611 | 45.1 |
| 60-120k | 109 | 72,436 | 4.15 | 10.17 | 109 | 41.7 |
| 120k+ | 0 | - | - | - | - | - |
```

For an apples-to-apples sanity check, the raw Fizeau logs can be paired by
terminal-bench task id against Claude Sonnet and GPT-5-family runs. The overlap
varies: `qwen/qwen3.6-27b-20260422` has timing for 87 tasks, while
`anthropic/claude-4.6-sonnet` and OpenRouter `openai/gpt-5.4-mini` each overlap
on 5 tasks. The OpenAI-provider `gpt-5.5` runs overlap on 23 tasks, which is a
more useful paired comparison. This is still paired by task id rather than
identical prompt replay, but provider/runtime differences are part of the
inference-stack claim.

```text
paired qwen baseline on Claude/GPT-5-mini shared tasks: 290 OpenRouter turns
| context bucket | turns | input median | ttft p50 | ttft p90 | decode tps p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0-10k | 280 | 4,486 | 0.80 | 1.82 | 60.3 |
| 10-30k | 10 | 10,877 | 1.13 | 3.02 | 69.5 |

paired anthropic/claude-4.6-sonnet comparator: 388 OpenRouter turns
| context bucket | turns | input median | ttft p50 | ttft p90 | decode tps p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0-10k | 296 | 5,040 | 1.82 | 3.16 | 1734.5 |
| 10-30k | 11 | 11,153 | 2.07 | 2.66 | 1471.0 |
| 30-60k | 81 | 37,812 | 2.36 | 3.80 | 1184.2 |

paired openai/gpt-5.4-mini comparator: 274 OpenRouter turns
| context bucket | turns | input median | ttft p50 | ttft p90 | decode tps p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0-10k | 206 | 2,848 | 0.91 | 1.82 | 173.5 |
| 10-30k | 68 | 17,131 | 0.90 | 1.40 | 160.5 |

paired gpt-5.5 comparator: 1,384 turns across 23 shared tasks
| context bucket | turns | input median | ttft p50 | ttft p90 | decode tps p50 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0-10k | 935 | 3,011 | 1.10 | 5.96 | 375.8 |
| 10-30k | 370 | 18,402 | 1.02 | 6.06 | 209.2 |
| 30-60k | 74 | 43,225 | 1.08 | 2.88 | 165.4 |
| 60-120k | 5 | 63,852 | 1.34 | 1.55 | 179.5 |
```

The TTFT numbers are the cleaner cross-model comparison. Decode tokens/sec is
client-observed stream throughput from session logs, and vendor/proxy streaming
can batch deltas; the Claude decode numbers in particular should be treated as
effective response throughput, not raw model-engine decode speed.

The same Fizeau corpus also has enough local-provider coverage to compare
inference servers directly:

```text
provider/model coverage with overlap against qwen/qwen3.6-27b-20260422:
| provider/model | turns | tasks | overlap with Qwen OpenRouter |
| --- | ---: | ---: | ---: |
| vllm / qwen3.6-27b-autoround | 1,776 | 78 | 77 |
| omlx / Qwen3.6-27B-MLX-8bit | 3,183 | 79 | 78 |
| llama-server / Qwen3.6-27B-UD-Q3_K_XL.gguf | 2,499 | 77 | 76 |
| ds4 / deepseek-v4-flash | 3,570 | 83 | 82 |
```

Focused paired local-provider scan:

```text
vllm / qwen3.6-27b-autoround
  overlap=77 tasks; 0-10k ttft_p50=15.17s decode=86.8 tps;
  10-30k ttft_p50=20.79s decode=59.7 tps

omlx / Qwen3.6-27B-MLX-8bit
  overlap=78 tasks; 0-10k ttft_p50=9.88s decode=16.3 tps;
  60-120k ttft_p50=23.34s decode=11.2 tps

llama-server / Qwen3.6-27B-UD-Q3_K_XL.gguf
  overlap=77 tasks; 0-10k ttft_p50=1.92s decode=19.8 tps;
  120k+ ttft_p50=4.13s decode=9.3 tps

ds4 / deepseek-v4-flash
  overlap=82 tasks; 0-10k ttft_p50=22.56s decode=24.2 tps;
  60-120k ttft_p50=271.34s decode=18.3 tps
```

Interpretation: this is strong evidence that the inference server path is a
major product variable. The local providers have broad task overlap, and their
TTFT/decode behavior differs by orders of magnitude even before separating model
quality from runtime implementation.

The generated Fizeau benchmark artifact
`/Users/erik/Projects/fizeau/docs/benchmarks/data/timing.json` reports the same
profile more conservatively, using Fizeau's existing report generator:

```text
fiz-openrouter-qwen3-6-27b: n_turns=6,357
| context bucket | n_ttft | ttft_p50 | n_decode | decode_tps_p50 |
| --- | ---: | ---: | ---: | ---: |
| 0-10k | 3,363 | 0.805 | 3,288 | 49.9 |
| 10-30k | 2,223 | 1.109 | 2,223 | 51.1 |
| 30-60k | 648 | 1.603 | 648 | 44.7 |
| 60-120k | 112 | 2.477 | 112 | 43.9 |
```

Interpretation for the post: on OpenRouter terminal-bench sessions, TTFT rises
about 3x from the shortest to longest measured bucket in the generated artifact
and about 3.8x in the broader raw scan. Median decode rate is relatively stable
through 30k, then falls in long-context buckets.

## What this proves and does not prove

This proves that current coding-agent stacks on this machine depend heavily on
prompt caching during real local usage: Codex has a 99.2% median per-turn
cached-input ratio across local sessions, and Claude's aggregate stats show a
97.2% cache-read share of cache-inclusive input. It also proves the request
shape is large enough that uncached prefill would dominate many turns.

It does not prove the cache-on/cache-off latency delta directly. Codex and
Claude logs expose cache counters, while fizeau timing exposes context-depth
latency and decode behavior. The public OpenAI and Anthropic docs provide the
latency/cost mechanism. A lucebox-specific result still needs `agentic-session`
runs with cache on/off or prefix-cache variants.

## Follow-up experiment

Run `agentic-session` against lucebox with at least two configs:

1. Prefix reuse off or baseline disabled.
2. Prefix reuse on with the same prompt/tool-result replay.

Record per turn:

- prompt tokens
- cached or reused prefix tokens, if exposed
- first-content latency
- wall time
- decode tokens per second
- context limit and cache settings from `/props`

The plot to add to the post is turn number on the x-axis, with prompt tokens and
wall or first-content latency on separate y-axes. The claim to test is whether
the uncached path grows roughly with total prompt size while the cached path
tracks only the appended suffix.
