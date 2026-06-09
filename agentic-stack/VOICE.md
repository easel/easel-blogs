# Blog Voice

This should read like one engineer writing up a problem after chasing it far
enough to have useful numbers.

The tone is practical, first person, and specific. It can be a little impatient
with bad abstractions, but it shouldn't sound like a launch post.

## What It Sounds Like

Start from the work:

- what was bothering me
- what I measured
- what hardware, software, or logs were involved
- what surprised me
- what I still don't know

The older blog posts usually open with a concrete problem, not a thesis
statement. They name the machine, stack, or service early. They are willing to
say "I don't know yet" when the numbers stop short.

For this post, start with the mismatch:

- I have been collecting hardware that should be able to run local models.
- I keep seeing reports that local inference is fast.
- I wondered if I was doing something wrong.
- The agent felt slow between steps, not while it was streaming.
- That sent me to the logs.

Do not open with "benchmark shapes" or "the discourse." Those are conclusions
from the investigation, not the reason to keep reading.

The useful sequence is:

1. I had a practical expectation.
2. My setup did not behave that way.
3. I wondered whether I was doing something wrong.
4. I checked the logs.
5. The logs changed the question.

That sequence is better than starting with a claim about benchmarks, local
models, or inference stacks. The post should feel like an investigation catching
up to a problem, not a thesis looking for evidence after the fact.

Use the first person when that's the honest source of the observation:

```text
I've been accumulating hardware capable of running local models for years. At
the same time, I kept seeing reports about how fast some local setup was. So I
kept wondering: is it just me?
```

Use "we" for shared measurements from the lab or repo work:

```text
We have enough Codex and Claude logs to see the shape of the cache behavior.
We don't have a perfect provider-controlled experiment, and I'm not going to
pretend otherwise.
```

## Sentence Feel

Use normal technical-blog English:

- contractions are fine
- short blunt sentences are fine
- longer mechanical explanations are fine when the mechanism matters
- a dry aside is fine after the concrete point has landed
- avoid em dashes in prose

Good:

```text
I would watch the agent sit between steps, not while it was writing. Waiting
happened before the next tool call, before the next patch, before the next useful
token.
```

Also good:

```text
The local run isn't fake. It's just answering a different question.
```

Bad:

```text
This benchmark unlocks a new understanding of the agentic inference landscape.
```

Also bad:

```text
The logs pointed at the gap.
```

Better:

```text
Digging into the agent session logs made the difference clear.
```

Prefer verbs that name what happened: watched, waited, checked, measured,
compared, replayed, counted. Avoid abstract verbs that make the prose sound like
a summary of itself.

## Section Titles

Section titles should sound like the investigation moving forward.

Use:

```text
The numbers looked real
The pause was between steps
Every turn gets bigger
The benchmark was measuring the easy part
```

Avoid:

```text
Benchmark shape problem
Provider and runtime differences
What the evidence does and doesn't prove
```

The bad versions are accurate, but they sound like outline labels. The good
versions make a reader want the next paragraph.

## Evidence

Numbers need provenance. Put the setup close to the claim.

Include the details that change how the reader should interpret the result:

- data source
- machine or provider
- model and quantization
- prompt length or context bucket
- number of turns or tasks
- timing metric
- caveat

Good:

```text
In the Fizeau terminal-bench logs, Qwen on OpenRouter has 0.80s median TTFT in
the 0-10k bucket and 4.15s in the 60-120k bucket.
```

Good:

```text
Codex session records show a 96.5% aggregate cached-input share. That's not a
model property. That's the serving stack avoiding repeated prefill.
```

Bad:

```text
Hosted providers are obviously better optimized.
```

If the measurement only gets partway there, say that directly:

```text
This doesn't isolate model from provider. That's fine for this question. The
thing I'm trying to explain is the latency a coding agent actually sees.
```

## Attitude

Be fair to the thing being criticized.

Local inference is useful. Public throughput benchmarks can be accurate. Hosted
providers can still be slow in the wrong workload. The point is to separate
decode speed from agent latency and show where each number applies.

Avoid dunking. Avoid grandstanding. Don't write like the post has discovered
the one true answer. A useful posture is closer to:

```text
Here are the numbers I could get. Here is what they explain. Here is where they
stop explaining things.
```

## Examples To Prefer

Opening:

```text
I've been accumulating hardware capable of running local models for years. A
3090 here, newer Apple Silicon there, access to bigger boxes when I could get
it. At the same time, I kept seeing breathless reports about how fast some local
setup was.
```

Transition:

```text
That sent me back to the logs. I was not mostly waiting on decode. I was waiting
on the cost of getting a long, growing session back through the server on every
turn.
```

Caveat:

```text
This is not an apples-to-apples model benchmark. It is closer to the thing I
care about: what a coding agent feels like when the context is already deep.
```

Closing:

```text
The fast-local-model reports were not wrong. They just did not explain the thing
I was waiting on.
```

## What To Cut

Cut sentences that:

- praise the post's own insight
- announce importance instead of showing a consequence
- use sales words for technical behavior
- turn one run into a universal rule
- summarize without adding a decision, caveat, or next step
- repeat the same rhythm for several paragraphs

Cut vague capability claims:

- claims that the workflow has no friction
- claims that the system handles broad workloads
- rank claims without a benchmark set
- claims that a change remakes the category
- readiness claims without naming the workload
- optimization claims without naming the optimization

Replace them with the operation:

```text
The cache hit means the server didn't reprocess most of the prefix.
```

Not:

```text
The platform delivers effortless long-context performance.
```
