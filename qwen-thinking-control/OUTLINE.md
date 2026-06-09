# Qwen Thinking Control

## Thesis

I wanted to use Qwen. In nothink mode it was steady across providers, but it
left performance on the table for harder reasoning work. Turning thinking on
should have been the answer. Instead, unbounded thinking ate the token budget,
truncated the answer, and made the benchmark worse. The fix was not a better
prompt. It was enforced budgeting: count the reasoning tokens, reserve room for
the reply, and force Qwen to close with the transition it was trained to follow.

## Intro

I wanted Qwen to be the model.

It was fast enough. It was available locally. It had a real thinking mode. In
nothink mode the results were boring in a good way: across lucebox, MLX, and
OpenRouter, Qwen3.6 landed in the same 71 to 74 percent band on ds4-eval-92.
That made it a nice engineering target. The stack changed, the quant changed,
and the score mostly did not.

The problem was that nothink also seemed to top out. The model stayed composed,
but the harder reasoning rows were where I wanted the extra help. Qwen's own
papers say the point of the model is that it can switch between normal answers
and thinking mode, so I turned thinking on.

That is where the simple story fell apart.

Thinking was not just slower. Left alone, it was worse. On OpenRouter, unbudgeted
thinking scored 48.9, well below the 72.8 nothink run. The model did not fail
because the reasoning was useless. It failed because the reasoning ran into the
token cap and left no parseable answer.

So this turned into a rabbit hole: Qwen papers, provider behavior, chat template
flags, `/no_think`, budget hints, token counters, and finally a force-close path
that made the model stop thinking while it still had room to answer.

## Sections

### 1. Nothink was boring, which was useful

- Same Qwen3.6-27B across lucebox, OpenRouter, and MLX.
- Nothink band: 70.7, 71.7, 72.8, 73.9.
- Thinking-token count was 0 on the clean runs.
- This made provider differences less important than expected for nothink.

### 2. Boring was not enough

- Nothink was consistent, but did not give the performance I wanted.
- The harder reasoning tasks were the reason to use Qwen in the first place.
- Qwen3's own framing is hybrid thinking and non-thinking, not one mode forever.

### 3. Thinking made it worse

- OpenRouter unbudgeted think: 48.9.
- 84 of 92 rows reasoned.
- 32 hit the length cap.
- The failure was truncation, not bad reasoning.

### 4. The provider flags were not portable

- `enable_thinking: false`, `thinking: disabled`, and `reasoning_effort: none`
  did not mean the same thing everywhere.
- OpenRouter ignored the nothink controls until `/no_think` was injected into
  the prompt.
- Practical rule: verify the returned thinking-token count.

### 5. A budget hint is not a budget

- Disabling thinking and limiting thinking are separate problems.
- `reasoning_effort` and `budget_tokens` are hints unless the server enforces
  them.
- OpenRouter ignored the budget fields in the tested path.

### 6. The fix was two caps and a trained close

- Phase-1 cap for reasoning.
- Combined cap for the whole response.
- Reply reserve so the answer still has room.
- Force-close when the reserve is reached.
- For Qwen3.x, use the trained wrap-up string from the Qwen3 technical report,
  not a bare `</think>`.

### 7. Budgeted thinking recovered the model

- OpenRouter budgeted think: 76.1, up from 48.9 unbudgeted and above 72.8
  nothink.
- MLX budgeted think: 83.7, above its 73.9 nothink.
- Force-close engaged on 44/92 OpenRouter rows and 50/92 MLX rows.

### 8. Where this leaves Qwen

- Use nothink for cheap, predictable answers.
- Use thinking for harder tasks, but enforce the budget.
- Check the mode the server actually delivered.
- Treat reasoning control as serving behavior, not just prompting.

## Closing

Qwen was not the problem. My control surface was.

Nothink gave me a stable baseline. Unbounded thinking gave me expensive
truncation. Budgeted thinking gave me the model I had been trying to use in the
first place.

The lesson is irritating but useful: reasoning is not a boolean. For Qwen, it is
a resource that has to be metered by the serving stack. If the server cannot
count it, reserve space after it, and close it on schedule, then "thinking mode"
is not really under control.
