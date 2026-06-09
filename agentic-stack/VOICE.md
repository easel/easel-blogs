# Blog Voice

This is a personal technical blog voice. It should sound like one engineer
writing up something he actually tried, not a content strategy document wrapped
around a benchmark.

The model to aim for is closer to a good engineering note from Simon Willison,
Mitchell Hashimoto, or an old personal sysadmin blog: concrete setup, plain
stakes, specific measurements, honest caveats, and enough narrative flow that
the reader can follow how the conclusion was reached.

## Core Shape

Start with the situation, not the thesis.

Good technical posts usually have a human reason for existing: I wanted to use a
tool, I expected a result, something did not match, so I investigated. That is a
better opening than explaining the category or naming the lesson up front.

Use this shape:

1. What I was trying to do.
2. What I expected.
3. What did not match.
4. What I checked.
5. What the evidence changed.
6. What I now think.

Do not turn that sequence into six one-sentence paragraphs. Let related ideas
stay together.

## Paragraphs

Stop writing outline prose.

A post should not read like fifty two-sentence blocks. Use paragraphs with
enough mass to carry a thought. A normal paragraph can be four to seven
sentences if the sentences belong together. Short paragraphs are useful for
emphasis, but if every paragraph is short, none of them land.

Combine sentences when they are part of the same move:

```text
I wanted Qwen to be the model. It ran locally, was fast enough, and had a real
thinking mode. In nothink, it was boring in the useful way: Qwen3.6-27B stayed
in the same band across lucebox, MLX, and OpenRouter on ds4-eval-92.
```

Avoid chopping that into:

```text
I wanted Qwen to be the model.

It ran locally.

It was fast enough.

It had a real thinking mode.
```

The first version has flow. Chopped-up prose sounds like generated drama.

## Voice

Use first person when the claim comes from your work:

```text
I kept seeing fast local runs while my own agent loop still felt slow.
```

```text
I asked for nothink, but the provider still let the model reason.
```

Use "we" only for shared lab work, shared code, or shared measurements. Do not
use it to create fake authority.

Contractions are normal. Use them whenever they sound like how you would say the
sentence:

- it's
- we're
- can't
- don't
- didn't
- wasn't
- weren't
- isn't
- aren't

Do not mechanically replace every formal phrase. Some sentences want "it is."
Most blog prose does not.

## Evidence

Put evidence close to the claim it proves or qualifies. Do not build a separate
evidence museum at the end and ask the reader to connect it back.

Good:

```text
On OpenRouter, unbudgeted thinking scored 48.9, below the 72.8 nothink run. The
run did not fail because the reasoning was useless. It failed because 32 of 92
rows hit the length cap and left no parseable answer.
```

Weak:

```text
The results demonstrate that reasoning control is important.
```

Numbers need context:

- benchmark or log source
- model and serving path
- mode or config
- sample size
- metric
- caveat

If the caveat changes how the reader should interpret the number, say it in the
same paragraph.

## Headings

Headings are navigation first. They should help the reader understand where the
post is going without turning every section into a punchline.

Armin Ronacher's titles are a good reference point: short, direct, sometimes
opinionated, but not trying too hard. "Pushing Local Models With Focus And
Polish" and "Content for Content's Sake" work because they name the concern in
plain language. Steve Yegge is the counterpoint: his titles and section moves
can be funny, ranty, and oversized, but that only works because the entire post
is operating in that register. Borrow the confidence, not the sprawl.

Use headings that are either:

- plain: `Nothink was stable`
- mechanical: `One cap can't control two phases`
- direct: `OpenRouter still let it think`

Avoid headings that sound like internal planning artifacts:

```text
Provider control portability
Budget enforcement mechanism
Benchmark shape problem
What the evidence supports
```

Also avoid forcing every heading into the same cute pattern. If the section is a
table of results, call it `The results`. If the section is a mechanism, call it
`How the force-close works`. A boring heading is better than a strained one.

## What To Cut

Cut sentences that:

- explain why the post is important
- praise the post's own insight
- restate the heading
- summarize before showing the evidence
- use a global claim when the evidence is one benchmark or one machine
- introduce a contrast just to sound punchy
- repeat the same reversal pattern as a rhythm

Cut stock phrases:

- "the discourse"
- "unlocking"
- "the landscape"
- "transformative"
- "optimized" without naming the optimization

Replace abstract verbs with concrete ones:

- watched
- checked
- counted
- replayed
- compared
- measured
- capped
- truncated
- cached
- streamed

## Good Blog Behavior

Good posts can admit mistakes. Simon Willison often writes in public with
updates and corrections when he misreads something. That makes the writing more
credible, not less. If a run was wrong, a provider ignored a flag, or a number
changed after rerunning with a pinned grader, say so plainly.

Good posts scope themselves. Mitchell Hashimoto often starts from his own
project, states that the method may not apply to everyone, and then uses a
concrete example to carry the argument. Do that here too. Do not imply a
universal rule when the evidence is one lab's run.

Good posts have connective tissue. The Discord example has it: a short setup,
then what changed, then how to try it. It does not turn every fact into a new
section. Blog posts need the same continuity, just with more room for evidence.

## Final Pass

Before calling a draft done, read it once for structure, not grammar:

- Are related sentences grouped into real paragraphs?
- Does the post start from the work instead of the thesis?
- Does every section move the investigation forward?
- Are the tables explained by nearby prose?
- Are caveats attached to the numbers they qualify?
- Does the ending land a technical judgment without turning into a manifesto?

Then run the sloptimizer audit.
