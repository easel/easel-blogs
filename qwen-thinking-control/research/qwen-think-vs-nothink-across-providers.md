# Qwen3.6 think vs nothink across providers: thinking helps, if you budget for it

*May 2026 · by [Erik](https://x.com/easel)*

We ran the same Qwen3.6-27B on ds4-eval-92 across four serving stacks, in both
think and nothink mode, graded on one pinned grader. Nothink is steady: a tight
71 to 74 percent band across all four stacks, no outliers. Thinking helps, but
only when the reasoning budget is enforced. Left unbounded, think mode runs its
reasoning straight into the token cap, the visible answer gets truncated, and the
score lands *below* nothink (48.9 percent on OpenRouter). Bound the reasoning and
force the close and it recovers to above nothink: OpenRouter went from 48.9 to
76.1, and the MLX serve hit 83.7 against its own 73.9 nothink. The part we did not
expect going in is that the controls are not portable. The same nothink request
that MLX and lucebox honored, OpenRouter quietly ignored until we forced the issue
client-side.

> [Hero image: Qwen3.6 ds4-eval bars, nothink flat across providers, think split high/low]

## TL;DR

- Nothink is stable across stacks: 70.7 (5090 Laptop), 71.7 (3090 Ti), 72.8
  (OpenRouter), 73.9 (MLX 8-bit). Verified zero thinking tokens on all four.
- Unbudgeted think on OpenRouter scored 48.9, below nothink. The reasoning ran to
  the cap and the answer got cut: 84 of 92 rows reasoned, 32 hit the length cap.
- Budgeted think recovers it. OpenRouter with a client-side force-close hit 76.1;
  MLX 8-bit with the same hit 83.7 (+10 over its nothink).
- Disabling thinking and limiting it are different problems. Limiting needs
  enforcement, not a hint: OpenRouter ignored `reasoning_effort` and
  `budget_tokens` outright.
- lucebox think is pending (a server-side thinking-channel bug is being fixed);
  that cell is not in the table yet.

## The numbers

All rows are ds4-eval-92, single seed, one grader (v0.2.7.dev0), committed in
`Luce-Org/luce-bench-baselines`.

| Serving | Mode | ds4-eval-92 | Note |
|---|---|---|---|
| RTX 5090 Laptop (lucebox, Q4_K_M) | nothink | 70.7 | 0 thinking tokens |
| RTX 3090 Ti (lucebox, Q4_K_M) | nothink | 71.7 | 0 thinking tokens |
| OpenRouter (opaque quant) | nothink | 72.8 | nothink enforced client-side |
| Mac Studio M2 Ultra (MLX 8-bit) | nothink | 73.9 | 0 thinking tokens |
| OpenRouter (opaque quant) | think, unbudgeted | 48.9 | 84/92 reasoned, 32 hit cap |
| OpenRouter (opaque quant) | think, budgeted | **76.1** | force-close on 44/92 |
| Mac Studio M2 Ultra (MLX 8-bit) | think, budgeted | **83.7** | force-close on 50/92 |
| lucebox (bragi/sindri) | think | _pending_ | channel bug being fixed |

The earlier version of this post reported different nothink numbers (a ~56 band
with an 8-bit MLX serve at 77 flagged as an outlier). Those were old-grader and
old-server runs. Re-run on the single pinned grader, the four nothink scores
collapse into the 71 to 74 band above and MLX is no longer the odd one out. We
are using only the v0.2.7.dev0 numbers here.

## Nothink is the same everywhere

The clean nothink comparison is the stable result. All four stacks land within
about three points of each other (70.7, 71.7, 72.8, 73.9), and the thinking-token
count is 0 on every one, so the control was honored on all four (more on how we
got OpenRouter to honor it below). Run Qwen3.6 nothink and the score does not move
much with the stack or the quant, which is a useful contrast with Gemma 4, where
[think and nothink are a wash](<Think vs nothink on Gemma 4 — same accuracy, 10x the latency.md>)
but the score swung a few points by provider.

The 8-bit MLX serve is at the top of the band at 73.9, not the 20-point outlier we
read off the old runs. Whatever that earlier gap was, it lived in the grader and
server versions, not in the weights.

## Controlling thinking across providers

The OpenRouter nothink row taught us something we should have checked sooner: the
request that turns thinking off is not honored everywhere, and a server that
ignores it fails quietly. The benchmark sends the same nothink request to every
endpoint and trusts the score. That trust is misplaced unless you verify the model
actually stopped thinking.

There is no single field that disables thinking across stacks, so luce-bench sends
three in every request and lets each server take the one it understands:

```json
"chat_template_kwargs": {"enable_thinking": false},
"thinking": {"type": "disabled"},
"reasoning_effort": "none"
```

The first is the vLLM, SGLang, and MLX convention. The second is the Anthropic
shape that lucebox reads. The third is the OpenAI and OpenRouter convention.
Disabling thinking is a template-level switch: `enable_thinking: false` makes the
chat template skip the thinking opener so the model never starts a `<think>`
block. `mlx_lm` applied it and produced clean nothink (zero thinking tokens, terse
answers, every case finishing on `stop`), and lucebox honored its own shape the
same way. OpenRouter's routed provider honored none of the three and reasoned
anyway. We only got a clean nothink out of it by injecting `/no_think` into the
prompt client-side, which is a chat-template token Qwen recognizes regardless of
what the request body says. With that injection the returned thinking-token count
dropped to 0 and the score settled into the band at 72.8.

The practical rule that falls out of this: do not trust the flag you sent, verify
the thinking-token count that came back. A nothink run with thinking tokens on most
of its rows is not a nothink run.

## Budgeting thinking is a separate problem

Disabling thinking and limiting thinking are not the same lever, and the second one
is where the headline result lives. Limiting needs *enforcement*. A budget the model
is merely asked to respect does nothing, because the reasoning is trained in, not
instruction-gated. There are two ways to actually enforce it:

- Server-side force-close, which is what lucebox does in its generation loop:
  count the output tokens, force the close before the cap, and reserve room for the
  visible answer. The
  [thinking-budget machinery](<Putting Qwen's thinking on a budget — counting tokens and forcing the close.md>)
  post covers the mechanism.
- Client-side force-close, which is new in luce-bench for providers we cannot
  reach into. It watches the streamed reasoning, detects when it goes over budget,
  aborts the request, and re-prompts the model with its own trained terminator so it
  wraps up instead of trailing off. The budget was ~8k reasoning tokens inside a 32k
  `max_tokens` cap with a 4k reply reserve.

The terminator is not a bare `</think>`. For Qwen3.x it is the trained wrap-up
phrase from the [Qwen3 technical report (arXiv 2505.09388)](https://arxiv.org/abs/2505.09388),
the same `thinking_terminator_hint` the model card carries, which the model learned
to treat as "thinking is done, answer now."

Native budget hints do not substitute for this on every provider. OpenRouter
ignored `reasoning_effort` (medium scored about the same as high) and did not honor
`budget_tokens` at all, which is exactly why the client-side force-close is the
lever for providers like it. With it engaged on 44 of 92 rows and 0 continuation
failures, OpenRouter think recovered from 48.9 to 76.1. On MLX the same enforcement
engaged on 50 of 92 rows, also 0 failures, and lifted think to 83.7.

## Why unbudgeted think scores below nothink

Turn thinking on with no enforced cap and Qwen3.6 on OpenRouter scored 48.9, more
than 20 points below its own nothink. It is not that thinking hurt the reasoning.
It is that the reasoning ran to the token cap and the answer got truncated: 84 of
92 rows reasoned, and 32 of those ran straight into the length cap with nothing
parseable left for the reply. You pay for the reasoning and lose the answer.

The per-area breakdown shows the truncation hit short-answer formats hardest. These
are the OpenRouter runs, nothink against unbudgeted and budgeted think:

| Area | nothink | think, unbudgeted | think, budgeted |
|---|---|---|---|
| hellaswag | 86 | 34 | 88 |
| longctx | 100 | 33 | 100 |
| gsm8k | 93 | 77 | 96 |
| truthfulqa | 80 | 51 | 77 |

The formats that want a short, committed answer (hellaswag, longctx) cratered worst
under unbudgeted think, because a multiple-choice or extraction answer is a few
tokens that never get emitted once the reasoning eats the cap. gsm8k held up better
since its answers are longer and the reasoning is doing real work. Enforce the
budget and every area recovers to nothink or above. The MLX budgeted run lands in
the same place (gsm8k 95, hellaswag 91, truthfulqa 79, longctx 100), so the
recovery is a property of the enforcement, not one provider.

## Takeaway

For Qwen3.6, turn thinking on, but enforce a reasoning budget with a reply reserve.
Unbudgeted think truncates and scores below nothink. Bound the reasoning, force the
close (server-side on lucebox, or client-side for providers that ignore the budget
hints), and leave room for the answer, and thinking buys you several points over
nothink (48.9 to 76.1 on OpenRouter, 83.7 on MLX against 73.9). And whatever mode
you ask for, verify the server delivered it by checking the returned thinking-token
count, because a provider that ignores the flag will hand you the wrong run with no
error. The lucebox think numbers are not in the table yet; a server-side
thinking-channel bug is being fixed and the cell goes in once those runs land.

---

*ds4-eval-92 from antirez/ds4 (MIT), run via luce-bench, single seed, one grader
(v0.2.7.dev0), committed in `Luce-Org/luce-bench-baselines`. Qwen3.6-27B Q4_K_M via
lucebox (RTX 3090 Ti, RTX 5090 Laptop), MLX 8-bit (Mac Studio M2 Ultra), and
OpenRouter (opaque quant). Budgeted-think runs used luce-bench's client-side
force-close (over-budget reasoning aborted and re-prompted with the model's trained
terminator); OpenRouter nothink used client-side `/no_think` injection. lucebox
think pending a thinking-channel fix. Methodology:
[Running the benchmarks](<Running the benchmarks — an intro to luce-bench.md>).
Project: [github.com/Luce-Org/lucebox-hub](https://github.com/Luce-Org/lucebox-hub).*

**Related**
- [Running the benchmarks: an intro to luce-bench](<Running the benchmarks — an intro to luce-bench.md>)
- [Putting Qwen's thinking on a budget: counting tokens and forcing the close](<Putting Qwen's thinking on a budget — counting tokens and forcing the close.md>)
- [Think vs nothink on Gemma 4: same accuracy, 10x the latency](<Think vs nothink on Gemma 4 — same accuracy, 10x the latency.md>)
- [Every model we've run on ds4-eval-92](<Every model we've run on ds4-eval-92.md>)
- [What `/props` tells you about a lucebox server](<What props tells you about a lucebox server.md>)
</content>
</invoke>
