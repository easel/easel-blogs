# Putting Qwen's thinking on a budget: counting tokens and forcing the close

*May 2026 · by [Erik](https://x.com/easel)*

Qwen3.6 is a strong reasoner when you let it think, and a problem when you try to
bound how much. We spent a while getting its thinking under control, and the
answer turned out to be unglamorous: count the output tokens ourselves and, when
the budget runs low, inject the wrap-up directive Qwen was trained to act on and
let it close its own reasoning block. A bare `</think>` token is not enough on its
own. Here's why the obvious approaches don't work and what does.

## The problem: one cap isn't enough

Qwen wraps its scratch work in `<think> … </think>`. Everything before the close
tag is reasoning; everything after is the visible reply. The chat template
pre-opens the block, so the model starts decoding already inside `<think>`.

A single `max_tokens` cap can't govern that. On a hard prompt the model spends
its entire budget inside `<think>` and never emits `</think>`, and the response
comes back with no parseable answer at all. Tighten the cap and you get the
opposite failure: the model closes `</think>` with no tokens left to actually
answer. Either way you've burned the compute and have nothing to show a user.

## What doesn't work

Asking nicely. "Answer briefly," "don't overthink," "stop reasoning after a few
steps" in the system prompt are ignored. Reasoning is trained in, not
instruction-gated. (Gemma 4 takes this even further, which is its own
[story](<Think vs nothink on Gemma 4 — same accuracy, 10x the latency.md>).)

Letting the model self-close on a budget. If you just cap reasoning length and
hope the model wraps up, it doesn't. It gets truncated mid-derivation and the
leftover budget produces a fragment, not an answer.

## What works: two caps and a forced close

We split the single cap into two. A **phase-1 budget** bounds the reasoning, a
**combined cap** bounds the whole response, and a **reply-budget reserve** sits
between them to guarantee room for the answer. A request opts in with a
`thinking` block (Anthropic-style) or `reasoning.effort` (OpenAI-style), and the
effort tiers come from the model card sidecar (Qwen3.6 ships
`low=4032 … max=81408`).

Then the part that actually tames it: the server **counts tokens as it decodes**
and forces the close itself. In the autoregressive loop it tracks
`generated = committed_now − committed_at_entry`, and when
`remaining = n_gen − generated` drops to the reply reserve, it starts overriding
the next sampled tokens with a fixed sequence.

The sequence is the important part. We tried injecting a bare `</think>` and it
doesn't reliably land. The model was mid-derivation, and a lone close tag tends to
leave it confused or restating its scratch work in the reply phase instead of
answering. What it actually responds to is a short natural-language wrap-up
sentence that ends with the close tag. For Qwen3.x that string is the one from the
[Qwen3 technical report (arXiv 2505.09388)](https://arxiv.org/abs/2505.09388), the same lead-in the model saw during
training when reasoning was cut short:

> Considering the limited time by the user, I have to give the solution based on the thinking directly now.
> `</think>`

(followed by two newlines). We tokenize that whole phrase once at startup (24
tokens including the `</think>`) and the budget hook overrides the sampled tokens
with it in order, one per step, until the sequence is exhausted. The sentence is
what flips Qwen from thinking into answering; the `</think>` at the end just marks
the boundary for our parser. Inject the directive on our schedule rather than the
model's, and its trained "wrap up now" behavior takes over with the reserved
tokens still in hand.

The phrase lives in the model card sidecar, not the code, so each architecture
ships the cue it was trained on. Qwen3.6 and Laguna carry the "Considering the
limited time" lead-in; Gemma 4 uses a different transition cue. The server takes
the sidecar string verbatim and does not auto-append a close tag, so the operator
controls whether the inject ends the block or just nudges the model to self-close.

Why this lands on Qwen and not on Gemma 4 comes down to what the template trained.
Qwen's no-think render is a closed, consumed block: literal `<think>\n\n</think>`
followed by two blank lines, and those trailing blank lines are themselves a
transition cue Qwen was post-trained on. The model learned "this exact sequence
means thinking is done, the visible answer comes next." Our forced close leans on
the same trained boundary. Gemma 4's equivalent is a community-derived prefill with
no trailing transition cue after the channel close, so a force-close drops the
cursor mid-context and the model picks up whatever its training distribution says
follows a closed thought channel, which on a hard derivation is usually more
reasoning, not a finalized answer.

We run this two ways:

- Level 2, the in-process force-close, overrides the next sampled tokens with the
  trained wrap-up sequence right in the generation loop. No reprompt, KV cache
  preserved, and the reply is higher quality because the reasoning is still in
  frame when the model answers. This is the path for Qwen3.5/3.6, Gemma 4, and
  Laguna.
- Level 1, the reprompt fallback, is for backends without the in-loop hook: when
  phase 1 ends with no `</think>`, build a fresh prompt with the reasoning plus an
  injected `</think>` and decode the reply. It works anywhere but costs a second
  prefill of the whole reasoning trace.

Level 2 fires first; Level 1 is the safety net.

## The gotcha: how much to reserve

The reply reserve is the knob that bit us. We inherited 512 tokens from
`ds4_eval.c`, which was sized for DeepSeek V4 Flash's terse answers. On Qwen (and
Gemma, and almost everything else) 512 tokens forced the close and then ran out
mid-answer, so the force-close "worked" and still produced garbage. Our Gemma
thinking probes were getting cut off mid-coordinate-geometry-proof. We raised the
default to 4096, which Qwen3.6 and the Gemma sidecars now ship. Terse models can
override it back down. Force-closing is necessary but not sufficient: you have to
leave the model enough runway to land.

## Where it leaves Qwen

With the two caps and the forced close, a thinking budget is finally a compute dial
on Qwen3.6. You set an effort tier, the model reasons up to it, and it reliably
produces an answer within the combined cap instead of trailing off inside
`<think>`. That's the opposite of what we found on Gemma 4, where the think/nothink
switch is mostly cosmetic; on Qwen the thinking is doing work, and the budget is
the lever that makes it usable.

---

*Mechanism: `docs/specs/thinking-budget.md` and
`docs/experiments/thinking-mechanism-explainer.md`. Force-close (Level 2) lives in
the Qwen3.5/3.6, Gemma 4, and Laguna backends; the reply-reserve default and the
ds4_eval.c history are in the spec. Project:
[github.com/Luce-Org/lucebox-hub](https://github.com/Luce-Org/lucebox-hub).*

**Related**
- [Running the benchmarks: an intro to luce-bench](<Running the benchmarks — an intro to luce-bench.md>)
- [Meet lucebox: a local AI inference engine optimized for consumer hardware](<Meet lucebox — a local AI inference engine optimized for consumer hardware.md>)
- [Think vs nothink on Gemma 4: same accuracy, 10x the latency](<Think vs nothink on Gemma 4 — same accuracy, 10x the latency.md>)
- [Every model we've run on ds4-eval-92](<Every model we've run on ds4-eval-92.md>)
- [Qwen3.6 think vs nothink across providers: thinking helps, if you budget for it](<Qwen3.6 think vs nothink across providers — thinking helps if you budget for it.md>)
