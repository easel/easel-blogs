# Agentic Stack Investigation

## Thesis

I kept seeing fast local-model results while my own coding-agent loops still
felt slow. Digging into the agent session logs made the difference clear. I was
not mostly waiting on decode. I was waiting between turns, where long-context
prefill, cache behavior, request setup, and serving-path details show up in the
timing.

Speed and model quality matter. They just are not the whole product.

## Intro

I've been accumulating hardware capable of running local models for years. A
3090 here, newer Apple Silicon there, access to bigger boxes when I could get
it. At the same time, I kept seeing breathless reports about how fast some local
setup was.

So I kept wondering: is it just me? What am I doing wrong?

The local numbers were real enough. A 3090 can run useful models. A 5090 can put
up silly-looking token numbers. Apple Silicon and DGX Spark are good enough that
speed and even model quality aren't the core issue anymore.

But those numbers still did not match my coding-agent experience. I would watch
the agent sit between steps, not while it was writing. Waiting happened before
the next tool call, before the next patch, before the next useful token.

That sent me back to the logs. I was not mostly waiting on decode. I was waiting
on the cost of getting a long, growing session back through the server on every
turn.

A coding agent keeps dragging the session forward: system prompt, tools, repo
context, tool calls, tool output, patches, test failures, and the next
instruction. Most of turn N is turn N-1 with a little more text on the end. If
the server reuses that prefix, the next step can start without paying for the
whole context again. If it doesn't, the agent waits.

So this is not a post about whether local models are good. They are. It is about
whether the local serving stack is built for the workload a coding agent
actually sends.

## Outline

### 1. The numbers looked real

Open with the hardware and public claims before criticizing anything.

- I have been collecting local-model-capable machines for years.
- Public results keep showing real speed on 3090, 5090, M5 Max, and DGX Spark
  class hardware.
- LocalMaxxing is useful because it records the machine, model, engine, prompt
  tokens, output tokens, TTFT, prefill, and output tok/s.
- The numbers are not fake. That is why the mismatch was confusing.

Use examples:

- RTX 5090 LocalMaxxing runs with short prompts and 140-240 output tok/s.
- 3090-class examples with useful Qwen-class decode.
- M5 Max and DGX Spark public benchmark posts with strong local throughput.

Reader question to answer:

If those numbers are real, why does the local coding agent still feel bad?

### 2. The pause was between steps

Move from benchmark claims to the local symptom.

- The agent was not slow while streaming a long answer.
- The painful gap was between steps.
- Waiting happened before the next tool call, patch, or useful token.
- That points at prefill, cache misses, request setup, context handling, and the
  serving path.

Point:

A local model can decode fast and still make an agent feel slow if the delay is
before decode starts.

### 3. Every turn gets bigger

Keep this mechanical, not abstract.

- Stable prefix: system prompt, tool definitions, policy, harness instructions.
- Growing history: user requests, assistant messages, tool calls, tool results,
  build logs, diffs, failed attempts, test output.
- Per-turn suffix: the next instruction or new observation.

Core mechanism:

Turn N is mostly turn N-1 plus a suffix. The serving stack either reuses the
shared prefix or pays to process most of the same text again.

### 4. Codex and Claude lean on cache

Use Codex and Claude local traces to test the premise.

- Codex full corpus: about 105k median per-turn input tokens, 99.2% median
  cached-input ratio, 96.5% aggregate cached-input share.
- Recent Codex slice: about 97k median per-turn input tokens, 99.0% median
  cached-input ratio.
- Claude local stats: 68.4B cache-read input tokens and 97.2% cache-read share
  of cache-inclusive input.

Point:

Codex and Claude are not fast because they avoid long prompts. They are usable
because most of the repeated prompt is cache-backed.

### 5. Context depth shows up in TTFT

Use Fizeau terminal-bench logs next.

- OpenRouter corpus: 7,247 turns.
- All OpenRouter TTFT rises from 0.86s at 0-10k input tokens to 3.26s at
  60-120k.
- Dominant Qwen OpenRouter model rises from 0.80s to 4.15s over the same range.
- Qwen decode drifts from 50.2 tok/s to 41.7 tok/s as context grows.

Point:

The delay I was seeing has a measurable shape. As context gets deeper, the next
turn takes longer to start.

### 6. Serving path changes the feel

This is where GPT-5.5, OpenRouter, and local providers fit.

- GPT-5.5: 23 overlapping terminal-bench tasks, 1,384 turns, TTFT around
  1.0-1.3s through 60k+ context, much higher decode than Qwen OpenRouter.
- Claude Sonnet and OpenRouter GPT-5 mini: only 5 overlapping tasks each, useful
  sanity checks, not a main comparison.
- Local providers: vLLM, OMLX, llama-server, and DS4 overlap Qwen OpenRouter on
  roughly 76-82 tasks.

Point:

This is not a clean model benchmark, and it should not be presented as one. It
is a comparison of the latency a coding-agent workload sees through different
serving paths.

What it shows:

- runtime and provider behavior matter
- cache and prefill behavior matter
- local providers can vary a lot on the same broad workload
- model quality alone does not explain the experience

### 7. The benchmark was measuring the easy part

Only now make the benchmark-shape critique.

- A "write a story" test is a small prompt followed by a long answer.
- It is fine for measuring decode.
- It does not measure the waiting I was seeing between agent steps.
- Long-prompt single-request tests are closer, but still miss repeated prefix
  reuse across turns.
- Terminal-Bench, SWE-bench agent runs, Fizeau logs, and `agentic-session`
  replay are the right shape.

Point:

The benchmark was answering a different question. That is why the local numbers
could be true while the agent still felt slow.

### 8. What the data supports

Supported:

- Real coding-agent sessions are huge and cache-heavy.
- Context depth changes TTFT and decode behavior.
- Provider and runtime paths change user-visible latency.
- Local serving stacks can be excellent at decode and still weak at agent loops.

Not yet proven:

- A clean cache-on/cache-off latency delta for the exact same replayed prompts.

Follow-up:

Run `agentic-session` with prefix reuse on and off. Plot prompt tokens, reused
prefix tokens, first-content latency, wall time, and decode rate by turn.

### 9. The missing local layer

This is where the post comes back to the stack without turning into a pitch.

- We cannot reproduce closed-vendor model RL just by downloading weights.
- We can own the inference engine, harness contract, model metadata, `/props`,
  cache settings, autotuning, evals, and replay tests.
- A local agent competes by making those layers work together for the loop the
  agent actually runs.

## Closing

This is why the fast-local-model reports bothered me. They were not wrong. They
just did not explain the thing I was waiting on.

For coding agents, speed and model quality are no longer enough to explain the
gap. The workload is long-context, prefix-reuse-heavy, and sensitive to the time
before the next turn starts. The systems that feel good are not just better
weights. They are serving stacks built around caching, prefill behavior, tool
protocols, and the harness loop.

That is the part the local stack has to match. Not because local models are bad,
but because the model is only one layer in the thing the user experiences.
