# Getting Qwen to stop thinking

*June 2026 · by [Erik LaBianca](https://x.com/easel)*

I wanted Qwen to be the model.

It was fast enough to keep in the loop, available locally, and had a real
thinking mode. In nothink mode it was also boring in the useful way:
Qwen3.6-27B landed in a tight band across lucebox, MLX, and OpenRouter on
`ds4-eval-92`. The stack changed, the quant changed, and the score mostly did
not.

That was the good part. The bad part was that nothink seemed to top out. It was
consistent, but the harder reasoning rows were exactly where I wanted more from
the model. Qwen's own technical report describes a model that can switch between
thinking mode and non-thinking mode, with a thinking budget to trade latency for
performance. That sounded like the thing I wanted.

So I turned thinking on.

That is where the simple story fell apart. Thinking was not just slower. Left
alone, it was worse. On OpenRouter, unbudgeted thinking scored 48.9, below the
72.8 nothink run. The model was not failing because the reasoning was useless.
It was failing because the reasoning ran into the token cap and left no
parseable answer.

This turned into the usual kind of rabbit hole: Qwen papers, provider behavior,
chat-template flags, `/no_think`, budget hints, token counters, and eventually a
force-close path that made the model stop thinking while it still had room to
answer.

## Nothink was boring

The clean nothink runs were almost suspiciously steady:

| Serving path | Mode | ds4-eval-92 |
| --- | --- | ---: |
| lucebox, RTX 5090 Laptop, Q4_K_M | nothink | 70.7 |
| lucebox, RTX 3090 Ti, Q4_K_M | nothink | 71.7 |
| OpenRouter, opaque quant | nothink | 72.8 |
| MLX 8-bit, Mac Studio M2 Ultra | nothink | 73.9 |

All four had zero thinking tokens once the control was actually honored. That
last clause matters. The first OpenRouter nothink attempts were not really
nothink. The request said nothink, but the provider still let the model reason.

This was the first practical lesson: the mode flag is not enough. Check the
returned thinking-token count. A nothink run with thinking tokens is just a
mislabeled run.

Once the mode was clean, the result was useful. Nothink Qwen was stable across
serving paths. That made it a good baseline and a bad excuse. If the model still
fell short on harder rows, the next lever was supposed to be thinking.

## The switch did not switch everywhere

The first annoying part was that "turn thinking off" did not mean one thing.

There are at least three knobs in the wild:

```json
"chat_template_kwargs": {"enable_thinking": false},
"thinking": {"type": "disabled"},
"reasoning_effort": "none"
```

MLX understood the chat-template setting. lucebox understood its own thinking
shape. OpenRouter did not honor any of those for the routed provider we tested.
Injecting `/no_think` into the prompt was the control that produced zero
thinking tokens there, because Qwen's chat template recognizes it directly.

This is not just API trivia. If the server silently ignores the nothink request,
the benchmark still runs and you get a number. It is just the wrong number.

That changed how I read every result. The score was not enough. I had to check
whether the model actually used the mode I asked for.

## Thinking was not a boolean

Qwen3 is built around the idea that one model can use non-thinking mode for
ordinary answers or spend extra tokens in thinking mode for harder work. The
technical report describes this as a unified framework, with mode switching and
a thinking budget. The Qwen3.6 model card we carried into lucebox had the same
shape: normal max tokens, complex-problem max tokens, and reasoning effort tiers
from low to max.

That sounds like a clean API. It was not.

Disabling thinking and limiting thinking are different problems. Disabling is a
chat-template problem: do not open the `<think>` block, or tell Qwen `/no_think`
before it renders the response. Limiting is a generation problem: once the model
is already inside `<think>`, somebody has to count tokens and make it leave.

A request field called `budget_tokens` or `reasoning_effort` is not a budget
unless the server enforces it. In the OpenRouter path we tested, those fields
did not stop the model from spending the response inside `<think>`.

That distinction took too long to internalize. Mode is template control. Budget
is serving control.

## Unbounded thinking ate the answer

The bad OpenRouter run made the failure obvious:

| Mode | ds4-eval-92 | Note |
| --- | ---: | --- |
| nothink | 72.8 | clean nothink, zero thinking tokens |
| think, unbudgeted | 48.9 | 84/92 reasoned, 32 hit the length cap |
| think, budgeted | 76.1 | force-close on 44/92 |

The unbudgeted run did not prove that thinking hurt Qwen. It proved that
unbounded thinking is a bad serving policy. The model spent the budget in the
scratchpad and never got to the answer format the grader could parse.

The per-area scores made that clear:

| Area | nothink | think, unbudgeted | think, budgeted |
| --- | ---: | ---: | ---: |
| hellaswag | 86 | 34 | 88 |
| longctx | 100 | 33 | 100 |
| gsm8k | 93 | 77 | 96 |
| truthfulqa | 80 | 51 | 77 |

Short-answer formats cratered. `hellaswag` and `longctx` wanted a compact,
parseable answer. The model did a lot of work, hit the cap, and never emitted
the part the grader needed. `gsm8k` held up better because the reasoning was
actually useful and the answers had more room to be recognized, but even there
the unbounded run left points on the table.

You pay for the reasoning and lose the answer. That is the worst possible
version of thinking mode.

## The cap has to leave room for the answer

The next trap was assuming one cap could govern the whole response.

Qwen's response has two phases:

1. reasoning inside `<think> ... </think>`
2. visible answer after `</think>`

A single `max_tokens` cap cannot control both. If the cap is loose, the model can
spend it all reasoning. If the cap is tight, the model can close the thinking
block with no room left to answer.

The useful contract is two caps plus a reserve:

- a phase-1 cap for reasoning
- a combined cap for the whole response
- a reply reserve kept for the visible answer

This is why the Qwen3.6 sidecar in lucebox has both normal and complex-problem
budgets:

| Tier | Reasoning budget |
| --- | ---: |
| low | 4,032 |
| medium | 16,128 |
| high | 32,256 |
| x-high | 56,832 |
| max | 81,408 |

Those are phase-1 budgets, not promises that the model gets the whole response
for scratch work. The server still needs to reserve reply tokens after the
thinking block. For Qwen3.6, the sidecar keeps a 4,096-token reply reserve. That
number is not sacred. It is just the lesson from watching terse-model defaults
cut verbose models off mid-answer.

## The close has to be trained

The fix was not "tell it to think less." That did not work. The fix was to make
the server responsible for the budget.

When the reasoning phase approaches the reply reserve, the server forces the
close. The exact close matters.

A bare `</think>` did not work well enough in our tests. Qwen was
mid-derivation, and a naked close tag could leave it confused or continuing the
derivation in answer space. The Qwen3 technical report includes the transition
string the model learned for this case:

```text
Considering the limited time by the user, I have to give the solution based on
the thinking directly now.
</think>
```

That is the string in the Qwen3.6 model-card sidecar. At startup, the server
tokenizes it. When the budget hook fires, the decode loop overrides the next
sampled tokens with that sequence. This is not asking the model politely. It is
moving the model onto a trained path: thinking is done, answer now.

The distinction is small but important. The close tag marks the boundary for the
parser. The natural-language lead-in is what tells the model how to behave after
the boundary.

## Providers need a fallback

Server-side force-close is the clean path because it happens inside the
generation loop. The server keeps the KV cache, the reasoning stays in frame,
and the reply starts with the model still looking at the work it just did.

When we control the backend, that path is available. Through a routed provider,
it usually is not.

For providers where we cannot touch the generation loop, luce-bench uses a
client-side fallback. It watches the streamed reasoning, aborts when the budget
is exhausted, and re-prompts with the same trained transition. That costs an
extra request and another prefill. It is still better than letting the answer
disappear into the token cap.

That fallback is what recovered the OpenRouter run. It engaged on 44 of 92 rows
and had zero continuation failures in the recorded result. The MLX budgeted run
used the same enforcement pattern: 50 of 92 rows force-closed, also with zero
continuation failures.

## Budgeted thinking recovered the model

Once the budget was enforced, the numbers looked like the model I had wanted in
the first place.

OpenRouter went from 48.9 unbudgeted to 76.1 budgeted. MLX 8-bit hit 83.7 with
budgeted thinking, up from its 73.9 nothink run.

The point is not that every task should use thinking. Nothink is still the right
mode for cheap, predictable answers. The point is that Qwen's thinking mode is
useful only when it is bounded by the serving stack. Without that, it is not a
reasoning control. It is an invitation for the model to spend the whole response
budget before saying the thing you asked for.

## Where this leaves Qwen

Qwen was not the problem. My control surface was.

Nothink gave me a stable baseline. Unbounded thinking gave me expensive
truncation. Budgeted thinking gave me the model I had been trying to use.

The lesson is irritating but useful: reasoning is not a boolean. For Qwen, it is
a resource that has to be metered. The server needs to know when thinking
started, how many tokens it has spent, how much reply budget remains, and how to
close the reasoning block without leaving the model stranded mid-derivation.

That is serving behavior, not just prompting. If the stack cannot count it,
reserve space after it, and close it on schedule, then "thinking mode" is not
really under control.

## Notes

The benchmark numbers here come from `ds4-eval-92`, single seed, one pinned
grader (`v0.2.7.dev0`), as captured in the research notes in this repo. The Qwen
mode-switching and thinking-budget behavior comes from the Qwen3 technical
report and the Qwen3.6 model-card values we transcribed into lucebox.

Primary references:

- Qwen3 technical report: https://arxiv.org/abs/2505.09388
- Qwen3.6 model card: https://huggingface.co/Qwen/Qwen3.6-27B
- Research note: `research/qwen-think-vs-nothink-across-providers.md`
- Mechanism note: `research/putting-qwen-thinking-on-a-budget.md`
- Spec: `research/thinking-budget-spec.md`
