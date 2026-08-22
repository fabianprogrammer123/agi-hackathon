# Landscape: Building blocks for long-running agents

_Researched 2026-08-22. Star counts and last-push dates pulled live from the GitHub API, not from blog posts._

## TL;DR — what to build on

For a **self-improving context hub**, the highest-leverage stack is:

1. **`ace-agent/ace`** — the reference implementation of the idea you're describing. Take its
   Generator / Reflector / Curator loop and its delta-update merge semantics.
2. **`getzep/graphiti`** — bitemporal knowledge graph, so "what did the agent believe on day 3"
   is answerable. This is what makes a *hub* rather than a *cache*.
3. **`letta-ai/letta`** — if you want a stateful-agent runtime rather than writing your own
   context-window compiler.

Everything else below is context for why those three.

---

## Tier 1 — Direct precedent for "self-improving context"

### `ace-agent/ace` — ★1,272, last push 2026-05-19, Python, Apache-2.0
The SambaNova / Stanford / UC Berkeley **Agentic Context Engineering** paper
([arXiv 2510.04618](https://arxiv.org/abs/2510.04618)) made runnable.

Treats the context as an **evolving playbook** rather than a prompt. Three roles:

| Role | Job |
| --- | --- |
| Generator | Produces reasoning trajectories on the task |
| Reflector | Distills concrete lessons from successes *and* errors |
| Curator | Merges lessons into the playbook as **delta updates** with helpful/harmful counters |

The delta-update + dedup design is the interesting part: it is an explicit defence against
**context collapse**, where naive "rewrite the whole prompt each round" loops degrade into mush.

Reported: +10.6% on agent tasks (AppWorld), +8.6% on finance (FiNER / XBRL), −82.3% adaptation
latency and −75.1% rollouts vs. GEPA.

**Why it's a good base:** adding a new task needs only three `DataProcessor` methods
(`process_task_data`, `answer_is_correct`, `evaluate_accuracy`). Orchestration, parallel eval and
aggregation are already there. Apache-2.0.

**Caveat:** last push was May 2026 — it is a research artifact, not a maintained product. Expect to
vendor it rather than depend on it.

Related: `ace-agent/ace-appworld` (★21), `wayne930242/Reflexive-Claude-Code` (★16, ACE-as-Claude-Code-skills).

### `EvoAgentX/EvoAgentX` — ★3,247, last push 2026-08-14, Python
Self-evolving *ecosystem* framework — evolves workflows and agent topologies, not just the context
blob. Broader and more speculative than ACE; useful if the hub should also rewrite its own routing.

---

## Tier 2 — Memory / knowledge substrate

### `mem0ai/mem0` — ★63,831, last push 2026-08-22, Python
The most-adopted memory layer. 2026 algorithm: single-pass extraction, entity linking, multi-signal
retrieval, temporal reasoning. Easiest on-ramp — library → self-hosted server → cloud, same API.
Best when you want memory to *just work* and spend your hackathon time on the improvement loop.

### `getzep/graphiti` — ★30,195, last push 2026-08-21, Python
Real-time **bitemporal** knowledge graphs. Tracks both when a fact was true and when the system
learned it, so contradictions and belief revision are first-class rather than a bug.

For a context hub this matters a lot: a self-improving system needs to *retract* bad lessons, and
"just overwrite" loses the audit trail that makes improvement legible to a judge.

### `topoteretes/cognee` — ★30,186, last push 2026-08-22, Python
Graph-native memory via an ECL (Extract → Cognify → Load) pipeline. Positions itself as a memory
*control plane*. Heavier than mem0, more opinionated than Graphiti.

### `basicmachines-co/basic-memory` — ★3,718, last push 2026-08-21, Python
Local-first, **plain-Markdown** memory over MCP. Underrated for a hackathon: the state is
human-readable files, so your demo can *show* the context improving in a diff. Very strong for
"here is what the agent learned" storytelling.

### `RedPlanetHQ/core` — ★1,949, TypeScript · `doobidoo/mcp-memory-service` — ★1,900, Python
Personal-AI-OS and MCP memory server respectively; the latter has autonomous consolidation built in.

### `langchain-ai/langmem` — ★1,621, last push 2026-08-11
Thin, LangChain-native. Fine if you're already in that ecosystem, not a reason to enter it.

---

## Tier 3 — Runtime / harness (keeping the agent alive for days)

### `letta-ai/letta` — ★24,352, last push 2026-08-16
Formerly MemGPT. **The** stateful-agent platform: self-editing memory, tiered context, sleep-time
compute. Its core thesis — the agent manages its own context window as a virtual memory hierarchy —
is the closest production-grade thing to "self-improving context hub".

Use it if you want a runtime; skip it if the hub *is* your contribution and you don't want its
opinions.

### `langchain-ai/langgraph` — ★40,247, last push 2026-08-22
Durable graph execution with checkpointing and interrupts. The pragmatic default for
pause/resume/human-in-the-loop.

### `agno-agi/agno` — ★41,835, last push 2026-08-22
Fast, batteries-included agent platform (sessions, memory, knowledge, monitoring). Good velocity.

### `OpenHands/OpenHands` — ★84,794, last push 2026-08-22, TypeScript
Full autonomous software-dev agent. Overkill as a dependency, excellent as a **source of ideas** for
long-horizon loop design and sandboxing.

### Durable execution layer
Temporal, Restate, Inngest, Hatchet, DBOS, Cloudflare Workflows. Deterministic replay from an event
history so a crash mid-run doesn't lose the agent. **Only worth it if the competition scores
crash-resilience** — otherwise it's a large tax on a short build.

---

## Tier 4 — Optimizers (the "improving" half)

### `stanfordnlp/dspy` — ★37,516, last push 2026-08-21
Programming, not prompting. GEPA / MIPRO optimizers. ACE explicitly benchmarks against GEPA and
claims to beat it on cost — so DSPy is both a **baseline to beat** and a component to steal from.

### `microsoft/agent-lightning` — ★17,602, last push 2026-08-22
Trains agents (RL / prompt optimization) with near-zero changes to existing agent code. The path if
you want actual weight-level improvement rather than context-level.

---

## Benchmarks worth wiring in

Judges reward measurement. Cheap, credible options:

| Benchmark | Measures |
| --- | --- |
| **LoCoMo** | Cross-session dialogue memory |
| **LongMemEval** | Long-span memory *updating* — the right target for a self-improving hub |
| **HaluMem** | Memory consistency / hallucination |
| **AppWorld** | Agent tasks; ACE's headline benchmark, so directly comparable |
| **Vending-Bench 2** (Andon Labs) | Long-horizon coherent operation over many steps |
| **METR HCAST / Time Horizons** | Task length an agent can sustain |

Reference points in 2026: ~92.5 on LoCoMo and ~94.4 on LongMemEval at ~6.9k tokens/query.
LoCoMo in particular is close to saturated — **LongMemEval and HaluMem are the more honest targets.**

Recent papers to cite: *MemRL* (self-evolving agents via runtime RL on episodic memory, 2026-01),
*AMA-Bench* (long-horizon memory for agentic apps), *Remember When It Matters* (proactive memory).

Curated lists: `TeleAI-UAGI/Awesome-Agent-Memory`, `VoltAgent/awesome-ai-agent-papers`,
`yxf203/Awesome-Efficient-Agents`.

---

## Read of the field — where the gap actually is

Everything above is strong at **storage and retrieval**. Almost nothing is strong at **curation
under contradiction**: deciding which lessons to keep, which to retire, and proving the context got
*better* rather than just bigger.

ACE is the only widely-known attempt, it's a 2025 paper with a research-grade repo, and its
evaluation is narrow (AppWorld + finance). That's the seam.

Concretely, a differentiated hackathon entry looks like:

- **Curation as the product.** Every playbook entry carries provenance, a helpful/harmful counter,
  and a retirement rule. Judges can watch entries get promoted and demoted.
- **Bitemporal, so improvement is auditable.** Graphiti under ACE's curator → you can replay the
  hub's belief state at any past moment and diff it. Nobody demos this.
- **Falsification, not just accumulation.** A loop that actively tries to *disprove* its own lessons
  and retires the ones that fail. This is the honest answer to context collapse and it demos well.
- **Multi-agent hub.** One context store, many agents contributing and consuming lessons — the
  "hub" framing earns its name only if it's shared.
- **Show the delta.** Markdown-backed state (basic-memory style) so the improvement is a visible
  `git diff`, not a claim in a slide.

The trap to avoid: building another memory store. That space has 60k-star incumbents and a judge
will have seen five of them the same day.
