# context-hub

**A self-improving context hub for long-running agents.**

Most agent memory systems are good at *storing* and *retrieving*. Almost none are good
at **curation under contradiction** — deciding which lessons to keep, which to retire,
and proving the context got *better* rather than merely *bigger*.

That is the gap this project aims at.

---

## The idea

A long-running agent accumulates lessons. Left alone, that accumulation degrades:
restatements pile up, stale advice outlives its usefulness, and the context window fills
with noise. This is **context collapse**, and it is the reason most "the agent
remembers!" demos stop working on day three.

`context-hub` treats the context as a **playbook** that is only ever changed through
small, journalled deltas:

```
Generator  →  attempts the task with the compiled playbook as context
Reflector  →  distils what actually happened into insights
Curator    →  turns insights into deltas: add, upvote, downvote, revise, retire
```

Separating these three is what stops the loop from marking its own homework. The naming
follows [ACE (Agentic Context Engineering, arXiv:2510.04618)](https://arxiv.org/abs/2510.04618).

### What's different here

- **Evidence, not accumulation.** Every entry carries a helpful/harmful tally and
  Laplace-smoothed confidence, so one lucky episode can't outrank a well-evidenced rule.
- **Retirement is a first-class operation.** Entries that keep failing are retired
  automatically; independent rediscovery revives them.
- **Revision supersedes, it doesn't erase.** The journal still explains why the wording
  changed.
- **Time travel.** `playbook.at(tick)` replays the journal to reconstruct what the agent
  believed at any past moment — so improvement is a *diff*, not a claim.
- **Budgeted compilation.** `playbook.render(budget)` ranks and truncates whole entries.
  A long-running agent can't carry everything it knows; ranking decides what it walks in
  with.

---

## Quickstart

```bash
uv venv --python 3.11
uv pip install -e ".[dev]"
uv run pytest
```

```python
from context_hub import Delta, Op, Playbook

pb = Playbook()
pb.apply(Delta(op=Op.ADD, content="Check the schema before writing SQL.", episode="ep-0"))
pb.apply(Delta(op=Op.ADD, content="Retry on any error.", episode="ep-1"))

# Evidence turns against the second lesson.
retry = next(e.id for e in pb.active() if e.content.startswith("Retry"))
for _ in range(3):
    pb.apply(Delta(op=Op.DOWNVOTE, entry_id=retry, episode="ep-2"))

print(pb.render())  # the retired lesson is gone
print(pb.at(2).render())  # ...but you can still see what it believed at tick 2
```

Running the full loop:

```python
from context_hub.loop import improve

result = improve(
    tasks,
    generator=my_generator,  # .run(task, context) -> str
    reflector=my_reflector,  # .reflect(episode, context) -> list[Insight]
    scorer=lambda task, out: 1.0 if out == expected[task] else 0.0,
)
print(result.mean_reward)
print(result.playbook.render())
```

---

## Layout

```
src/context_hub/
  playbook.py   # entries, deltas, dedup, retirement, replay, persistence
  roles.py      # Generator / Reflector / Curator protocols + DefaultCurator
  loop.py       # the improvement loop
tests/          # deterministic, no API key required
docs/RESEARCH.md  # landscape survey: what exists, what to build on, where the gap is
```

`DefaultCurator` is deliberately conservative — it only admits new lessons from episodes
that actually succeeded. An agent that failed usually cannot tell you why.

---

## Status

Early. The playbook core and loop are implemented and tested; the LLM-backed Generator
and Reflector are next, followed by benchmark harnesses.

See [`docs/RESEARCH.md`](docs/RESEARCH.md) for the survey of existing work
(ACE, Letta, Graphiti, mem0, cognee, DSPy) and the reasoning behind this design.

## License

MIT
