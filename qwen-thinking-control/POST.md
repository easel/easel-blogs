# Getting Qwen to stop thinking

*June 2026 · by [Erik](https://x.com/easel)*

I wanted Qwen to be the model. It ran locally, was fast enough, and had a real
thinking mode. In nothink, it was boring in the useful way: Qwen3.6-27B stayed
in the same band across lucebox, MLX, and OpenRouter on `ds4-eval-92`.

| Serving path | Mode | ds4-eval-92 |
| --- | --- | ---: |
| lucebox, RTX 5090 Laptop, Q4_K_M | nothink | 70.7 |
| lucebox, RTX 3090 Ti, Q4_K_M | nothink | 71.7 |
| OpenRouter, opaque quant | nothink | 72.8 |
| MLX 8-bit, Mac Studio M2 Ultra | nothink | 73.9 |

That was a good baseline, but it wasn't enough. The rows I cared about were the
ones where I wanted the model to reason, so I turned thinking on. The first
result was worse.

| Mode | ds4-eval-92 | Note |
| --- | ---: | --- |
| nothink | 72.8 | clean nothink, zero thinking tokens |
| think, unbudgeted | 48.9 | 84/92 reasoned, 32 hit the length cap |
| think, budgeted | 76.1 | force-close on 44/92 |

That sent me into the gory details: Qwen papers, provider flags, `/no_think`,
budget hints, model cards, token counters, and forced closes. The short version
is that Qwen wasn't the problem. My control surface was.

## OpenRouter still let it think

The first bug was boring and important. I asked for nothink, but OpenRouter's
routed provider still let the model think. There isn't one portable switch:

```json
"chat_template_kwargs": {"enable_thinking": false},
"thinking": {"type": "disabled"},
"reasoning_effort": "none"
```

MLX honored the chat-template flag. lucebox honored its own thinking field.
OpenRouter honored none of those in the path I tested. The thing that worked was
putting `/no_think` in the prompt, which Qwen's template recognizes directly.
After that, returned thinking tokens dropped to zero and the score landed in the
same nothink band as the local runs.

The lesson here is plain: don't trust the request. Check the response. If a
nothink run has thinking tokens, it's not a nothink run.

## Budget fields weren't enforced

Turning thinking on uncovered the second bug. `reasoning_effort` and
`budget_tokens` sound like controls, but they're only controls if the serving
stack enforces them. In the OpenRouter path I tested, they didn't. Qwen kept
reasoning until the response hit the token cap. The grader wasn't seeing bad
answers. It was often seeing no parseable answer at all.

The per-area scores made the failure mode obvious:

| Area | nothink | think, unbudgeted | think, budgeted |
| --- | ---: | ---: | ---: |
| hellaswag | 86 | 34 | 88 |
| longctx | 100 | 33 | 100 |
| gsm8k | 93 | 77 | 96 |
| truthfulqa | 80 | 51 | 77 |

`hellaswag` and `longctx` need short, committed answers. Unbounded thinking ate
the budget before those answers appeared. `gsm8k` held up better because the
reasoning was doing useful work, but it still improved once the budget was
enforced. This wasn't "thinking hurts Qwen." It was "unbounded thinking is a bad
serving policy."

## One cap can't control both phases

Qwen's thinking response has two phases: reasoning inside `<think> ... </think>`
and visible answer after `</think>`. A single `max_tokens` cap can't control
both. If the cap is loose, the model can spend it all in `<think>`. If the cap
is tight, the model can close the thought block with no room left to answer.

The serving stack needs three numbers:

- a reasoning cap
- a total response cap
- a reply reserve

For Qwen3.6, the model-card sidecar has these reasoning tiers:

| Tier | Reasoning budget |
| --- | ---: |
| low | 4,032 |
| medium | 16,128 |
| high | 32,256 |
| x-high | 56,832 |
| max | 81,408 |

The sidecar also reserves 4,096 tokens for the visible answer. I kept
underestimating that reserve. A force-close that leaves no answer budget still
fails.

## The server has to close the thought

The fix wasn't a better prompt. "Think less" doesn't do much once the model is
inside the reasoning trace. The server has to count generated tokens, and when
reasoning gets close to the reply reserve, it has to force Qwen out of
`<think>`.

A bare `</think>` wasn't enough in my tests. It marked the boundary for the
parser, but it didn't always move the model cleanly into answer mode. The Qwen3
technical report has the phrase Qwen was trained to use when reasoning is cut
short:

```text
Considering the limited time by the user, I have to give the solution based on
the thinking directly now.
</think>
```

That phrase lives in the Qwen3.6 sidecar. lucebox tokenizes it at startup. When
the budget hook fires, the decode loop overrides the next sampled tokens with
the sidecar sequence. Rather than asking Qwen to wrap up, the server puts it on
the trained "wrap up now" path.

When we control the backend, that can happen inside the generation loop. KV
state stays intact and the model answers with the reasoning still in frame.
When we don't control the backend, luce-bench uses a rougher fallback: watch the
stream, abort when the reasoning budget is gone, and re-prompt with the same
trained close. That costs another request. It's still better than letting the
answer vanish into the cap.

## Budgeted thinking was the useful mode

Once the budget was enforced, Qwen looked like the model I had been trying to
use. OpenRouter went from 48.9 unbudgeted to 76.1 budgeted. MLX 8-bit hit 83.7
with budgeted thinking, up from 73.9 nothink. The OpenRouter force-close fired
on 44 of 92 rows. The MLX run fired on 50 of 92. Both recorded zero continuation
failures.

Nothink is still useful. It's cheap, steady, and easy to compare across
providers. But for the harder rows, Qwen's thinking mode needs an actual meter.
Without one, "thinking" just means "spend the answer budget in scratch space."

## Where this leaves Qwen

Qwen wasn't the problem. Nothink gave me a stable baseline. Unbounded thinking
gave me expensive truncation. Budgeted thinking gave me the model I wanted to
use.

The useful lesson is that reasoning isn't a boolean. For Qwen, it's a resource
the serving stack has to meter. A server needs to know when thinking started,
how many tokens it has spent, how much reply budget remains, and how to close
the reasoning block without stranding the model mid-derivation. That's serving
behavior, not just prompting. If the stack can't count it, reserve space after
it, and close it on schedule, then thinking mode isn't under control.

## Notes

The benchmark numbers here come from `ds4-eval-92`, single seed, one pinned
grader (`v0.2.7.dev0`). The Qwen mode-switching and thinking-budget behavior
comes from the Qwen3 technical report and the Qwen3.6 model-card values
transcribed into lucebox.

Primary references:

- Qwen3 technical report: https://arxiv.org/abs/2505.09388
- Qwen3.6 model card: https://huggingface.co/Qwen/Qwen3.6-27B
