# The agentic stack is the product, not the model

*May 2026 · by [Erik LaBianca](https://x.com/easel)*

I used to think the model was the thing. Swap in a better model, get a better agent.

After enough time staring at agent traces and serving configs, that stopped holding up. A coding agent is a stack. The quality you see at the top comes from every layer below it: context, guardrails, tool use, the harness, the inference engine, and finally the model. The closed agents that feel good to use seem to understand this. They build the layers together.

This post is the version of that argument I wish I had read a year ago: what the layers are, why vertical integration helps, and where a local open-weights stack like lucebox can still compete. This is a thinking piece more than a results piece. The numbers that ground it live in the linked posts.

## The stack, top to bottom

The usual conversation collapses the whole agent into "the model" and then argues about benchmarks. Naming the layers makes the product clearer:

1. Context. Deciding what work to do and assembling the right material for it: files, history, task framing.
2. Guardrails. Tests, type checks, and other ways to verify the work against something stronger than the model's opinion.
3. Implementation. The patch or artifact itself.
4. Self-discovery. The loop where the agent runs tools, reads failures, and corrects itself.
5. The harness. System prompts, tools, sandboxing, model selection, tuning, and routing.
6. The inference engine. Prompt caching, KV cache, prefix cache, prefill, decode, and streaming.
7. The model. Reasoning, pretraining, reinforcement learning, and the raw prefill and decode behavior of the weights.

Those look like separate concerns. In practice, they are coupled. Context quality depends on the harness. Guardrails only matter if the agent can run them and use the result. Self-discovery only works if tool calls execute cleanly and the next turn comes back fast enough that iteration stays cheap.

That is where the inference engine stops being plumbing. Multi-turn agents resend most of the same prompt on every turn. Turn N is usually turn N-1 plus a suffix: one more tool result, one more instruction, one more attempted fix. If the engine re-prefills the whole transcript each time, the agent pays the same long-context cost again and again. If the engine reuses the shared prefix, the loop gets faster, cheaper, and more willing to iterate.

The product difference is visible at the top. A good model behind bad context writes confident wrong patches. A good harness behind an engine that misses cache reuse produces an agent that may be correct, but slow enough that it iterates less. Fewer iterations means fewer chances to discover and fix mistakes. The multi-turn loop is where this compounds, and it is what we tried to isolate in the [agentic-session work](<Multi-turn agentic loops as a benchmark target — what they look like, why they matter, what we've measured.md>): context grows monotonically, every turn depends on cache behavior, and latency is paid once per turn for the whole session.

## Why owning the whole stack helps

The leading closed agents, Claude Code and OpenAI's Codex among them, own the stack end to end. The same vendor builds the model, serves it through its own inference stack, and drives it with its own harness. That overlap matters in two ways that are visible from public descriptions, without relying on inside knowledge.

The first is training the model on its own harness. When one organization controls both reinforcement learning and the tool protocol, it can reward the exact behavior its harness expects: this system prompt shape, these tool calls, these recovery patterns. The model is not trained for abstract tool use. It is trained for the protocol it will actually see.

Open weights do not get that for free. A capable model dropped into a different harness may be asked to emit a tool-call syntax it was never rewarded for. We see that mismatch in our forge numbers: the same Gemma 4 26B that scores well behind a proper tool-use protocol on OpenRouter scores zero through a path that asks for a tool-call shape it was not trained to produce.

The second mechanism is caching co-design between the harness and the inference engine. Prompt caching, prefix caching, and KV reuse pay off when consecutive requests share a long prefix. Whether they do is mostly a harness decision: where stable system content goes, whether new context is appended instead of rewriting earlier turns, how tool results are ordered, and how much of the conversation stays byte-for-byte stable.

An integrated vendor can shape prompts so the cache underneath them hits, then tune the cache for the prompt shapes it knows it will receive. The harness and engine become one performance system. A harness that does not know the engine's cache rules leaves latency on the table. An engine that cannot see the harness's prompt structure leaves cost on the table. Owning both lets the vendor collect that win.

None of this needs mystery. Once one company controls the model, harness, and serving stack, these are the obvious optimizations to take.

## Where lucebox sits

The open-weights constraint is simple: we do not own the model's reinforcement learning. We download weights someone else trained. We cannot reinforce luce-bench's tool protocol into the model, and the forge result above is the reminder. The model may be capable, but it was not tuned for our path.

What we can own is the lower stack, and we can make those layers agree with each other.

The inference engine is ours. [lucebox](<Meet lucebox — a local AI inference engine optimized for consumer hardware.md>) is built around the caching and prefill machinery that agent loops need: prefix cache, KV cache with configurable dtypes, pFlash prefill, and DFlash speculative decode. Multi-turn loops are useful on a 24 GB card because each new request mostly repeats the previous one. That is the case prefix caching is built for. We cannot train the model to produce cache-friendly prompts, but we can make the engine reuse the prefix the loop actually sends.

The eval and harness tooling is ours too. [luce-bench](<Running the benchmarks — an intro to luce-bench.md>) is how we see the layers we control. The agent and forge areas check whether tool calls come out in the right shape. Agentic-session replays a fixed tool-result history to isolate how the engine behaves as context grows. We cannot reward the model for good tool calls, but we can measure where the protocol mismatch bites and shape the harness around it.

The layer contract is ours, and it may be the most important part. Closed vendors close the harness-to-engine gap by owning both ends. We close it by making the engine describe its config and making the harness read that description. The [model card](<Model cards in lucebox — a typed sidecar for what the server actually needs.md>) states what a model needs. [`/props`](<What props tells you about a lucebox server.md>) lets the harness discover the engine's running config, context limit, cache settings, and budgets instead of guessing. The [autotuner](<How lucebox auto-tunes itself to your GPU.md>) tunes the engine to the hardware the loop runs on.

That is a different route to the same goal: get the harness and engine to agree on reality so caching pays off and the loop stays responsive.

The accounting has two columns. We give up the model's RL, an advantage we cannot reproduce from outside the weights. We keep the inference engine, eval tooling, and interfaces between layers, and we co-design those as one system. A local open stack closes part of the gap by integrating tightly across the layers it controls. The place that integration matters most is the multi-turn loop, which is why the [agentic-session](<Multi-turn agentic loops as a benchmark target — what they look like, why they matter, what we've measured.md>) suite is where the harness-and-engine cache design has to prove itself.

The model was never the whole product. It is the bottom layer of a stack, and on the layers above it we can still compete.

---

This is opinion grounded in what we've built and measured. The supporting numbers live in the linked posts and in `Luce-Org/luce-bench-baselines`. The characterization of how vertically integrated vendors operate is read from their public descriptions of their own systems, not private knowledge. Scope it to what it is: one lab's view from the open-weights side of the line.

**Related**
- [Multi-turn agentic loops as a benchmark target: what they look like, why they matter, what we've measured](<Multi-turn agentic loops as a benchmark target — what they look like, why they matter, what we've measured.md>)
- [Meet lucebox: a local AI inference engine optimized for consumer hardware](<Meet lucebox — a local AI inference engine optimized for consumer hardware.md>)
- [How lucebox auto-tunes itself to your GPU](<How lucebox auto-tunes itself to your GPU.md>)
- [What `/props` tells you about a lucebox server](<What props tells you about a lucebox server.md>)
- [Model cards in lucebox: a typed sidecar for what the server actually needs](<Model cards in lucebox — a typed sidecar for what the server actually needs.md>)
