# The agentic stack is the product, not the model

*May 2026 · by [Erik](https://x.com/easel)*

I've been accumulating hardware capable of running local models for years. A
3090 here, newer Apple Silicon there, access to bigger boxes when I could get
it. At the same time, I kept seeing breathless reports about how fast some local
setup was.

So I kept wondering: is it just me? What am I doing wrong?

The local numbers were real enough. A 3090 can run useful models. A 5090 can put
up silly-looking token numbers. Apple Silicon and DGX Spark are good enough that
speed and even model quality aren't the core issue anymore.

But those numbers still didn't match my coding-agent experience. I would watch
the agent sit between steps, not while it was writing. Waiting happened before
the next tool call, before the next patch, before the next useful token.

Digging into the agent session logs made the difference clear. I wasn't mostly
waiting on decode. I was waiting between turns, where long-context prefill,
cache behavior, request setup, and serving-path details show up in the timing.

## The numbers looked real

The fast-local-model reports weren't fake. That's why the mismatch was annoying.

LocalMaxxing has plenty of real runs from real machines. Some 5090 entries show
short-prompt decode in the 140 to 240 tok/s range. 3090-class cards can run
useful Qwen-class models. M-series Macs and DGX Spark are good enough that
"local is too slow" doesn't explain the whole problem.

But a lot of those runs are shaped like this:

```text
small prompt -> long answer -> output tokens per second
```

That's a perfectly good decode test. It answers "how fast can the model keep
talking once it starts?"

It doesn't answer the thing I was feeling in an agent loop.

## The pause was between steps

My local agent wasn't painful while streaming a long answer. The painful gap was
between steps.

It showed up before the next tool call, before the next patch, before the next
useful token. That points at prefill, cache misses, request setup, context
handling, and the serving path.

A model can decode fast and still make an agent feel slow if the delay happens
before decode starts.

## Every turn gets bigger

A coding agent keeps dragging the session forward:

- system prompt
- tool definitions
- repo context
- prior assistant messages
- tool calls
- tool output
- patches
- test failures
- the next instruction

Most of turn N is turn N-1 with a little more text on the end. If the server can
reuse that shared prefix, the next step can start without reprocessing the whole
session. If it can't, every tool loop pays long-context prefill again.

That makes coding agents prefix-reuse workloads. Decode matters, but it isn't
the whole wait.

## Codex and Claude lean on cache

The local session logs weren't small.

Across the Codex corpus on this machine, the median per-turn input was about
105k tokens. The median cached-input ratio was 99.2 percent, and cached tokens
were 96.5 percent of aggregate input.

The recent Codex slice told the same story: about 97k median per-turn input,
with a 99.0 percent median cached-input ratio.

Claude's local stats were even more blunt: 68.4B cache-read input tokens, with a
97.2 percent cache-read share of cache-inclusive input.

Those agents aren't staying usable by sending short prompts. They're staying
usable because most of the repeated prompt is cache-backed.

## Context depth shows up in TTFT

The Fizeau terminal-bench logs showed the timing curve.

Across 7,247 OpenRouter turns, median time to first token rose as input context
got deeper:

| Input tokens | Median TTFT |
| --- | ---: |
| 0-10k | 0.86s |
| 10-30k | 1.11s |
| 30-60k | 2.03s |
| 60-120k | 3.26s |

The dominant Qwen OpenRouter model had the same shape:

| Input tokens | Median TTFT | Median decode |
| --- | ---: | ---: |
| 0-10k | 0.80s | 50.2 tok/s |
| 10-30k | 1.11s | 51.2 tok/s |
| 30-60k | 1.67s | 45.1 tok/s |
| 60-120k | 4.15s | 41.7 tok/s |

That doesn't isolate cache on and off. It does show the thing I was waiting on:
as context gets deeper, the next turn takes longer to start.

## Serving path changes the feel

This isn't a clean model benchmark, and it shouldn't be presented as one. It's a
comparison of what a coding-agent workload feels like through different serving
paths.

The GPT-5.5 paired runs made the point. Across 23 overlapping terminal-bench
tasks and 1,384 turns, TTFT stayed around 1.0 to 1.3 seconds through 60k+
context. Decode was much higher than the Qwen OpenRouter baseline.

The local-provider overlap was also broad enough to be useful:

| Serving path | Turns | Overlapping tasks |
| --- | ---: | ---: |
| vLLM Qwen autoround | 1,776 | 77 |
| OMLX Qwen 8-bit | 3,183 | 78 |
| llama-server Qwen GGUF | 2,499 | 76 |
| DS4 | 3,570 | 82 |

Those paths didn't feel the same. vLLM, OMLX, llama-server, OpenRouter, and
GPT-5.5 all put different latency and decode profiles under roughly similar
agent workloads.

That's stack behavior. Model quality alone doesn't explain it.

## The benchmark was measuring the easy part

This is where the public throughput numbers started to make sense.

A "write a story" test is a small prompt followed by a long answer. It measures
decode after the model is already talking. Long-prompt single-request tests are
closer because they measure prefill and TTFT, but they still miss repeated
prefix reuse across turns.

The agent workload is different. It is prompt-heavy, prefix-reuse-heavy, and
latency-sensitive at every step. Terminal-Bench, SWE-bench-style agent runs, and
captured terminal-agent logs are closer to the right shape.

So the benchmark wasn't wrong. It was answering a different question.

## What the data supports

The evidence points to a narrower claim than "local is bad" or "hosted is
magic."

It shows this:

- real coding-agent sessions are huge and cache-heavy
- context depth changes TTFT and decode behavior
- provider and runtime paths change user-visible latency
- local serving stacks can be excellent at decode and still weak at agent loops

It doesn't yet prove a clean cache-on/cache-off latency delta for the same
replayed prompts. The gold-standard run would replay the same agent session with
prefix reuse on and off, then plot prompt tokens, reused prefix tokens,
first-content latency, wall time, and decode rate by turn.

That caveat matters. It keeps the claim scoped to what the logs actually show.

## The missing local layer

The open-weights constraint is real. We don't own the model's reinforcement
learning. We can't train the exact Codex or Claude tool loop into downloaded
weights after the fact.

But we can own the layers around the model:

- inference engine
- harness contract
- model metadata
- `/props`
- cache settings
- autotuning
- evals
- replay tests

That's where local stacks have to compete. Not by pretending decode throughput
is the whole loop, and not by waving away the model. The model matters. It just
isn't the whole product.

This is why the fast-local-model reports bothered me. They weren't wrong. They
just didn't explain the thing I was waiting on.

For coding agents, speed and model quality aren't enough to explain the gap. The
workload is long-context, prefix-reuse-heavy, and sensitive to the time before
the next turn starts. Systems that feel good aren't just better weights. They're
serving stacks built around caching, prefill behavior, tool protocols, and the
harness loop.

That's the part the local stack has to match. Not because local models are bad,
but because the model is only one layer in the thing the user experiences.

## Notes

The local session measurements came from structured Codex and Claude usage
records on my machine. I counted token usage and cache counters, not transcript
content. The Fizeau measurements came from structured terminal-bench run logs:
request timestamp, first streamed delta, response timestamp, input tokens, and
output tokens.

External references:

- LocalMaxxing: https://www.localmaxxing.com/en
- LocalMaxxing API docs: https://www.localmaxxing.com/en/api-docs
- Presenc AI local LLM benchmark: https://presenc.ai/research/local-llm-tokens-per-second-benchmarks-2026
- Hardware Corner RTX 3090 LLM benchmarks: https://www.hardware-corner.net/gpu-llm-benchmarks/rtx-3090/
- Qwen 3.6 27B on RTX 3090: https://openclawdc.com/blog/best-local-llm-rtx-3090/
