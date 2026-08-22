"""The improvement loop: act, judge, curate, repeat."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from context_hub.playbook import Playbook
from context_hub.roles import Curator, DefaultCurator, Episode, Generator, Reflector


@dataclass
class RunResult:
    playbook: Playbook
    episodes: list[Episode]

    @property
    def mean_reward(self) -> float:
        return sum(e.reward for e in self.episodes) / len(self.episodes) if self.episodes else 0.0


def improve(
    tasks: Iterable[str],
    *,
    generator: Generator,
    reflector: Reflector,
    scorer: Callable[[str, str], float],
    playbook: Playbook | None = None,
    curator: Curator | None = None,
    char_budget: int = 4000,
) -> RunResult:
    """Run each task, learn from it, and carry the improved context into the next.

    ``scorer`` takes ``(task, output)`` and returns a reward in ``[0, 1]``. Keeping it
    a plain callable means the loop works with an exact-match check, a rubric, or a
    judge model without knowing the difference.
    """
    pb = playbook if playbook is not None else Playbook()
    cur = curator if curator is not None else DefaultCurator()
    episodes: list[Episode] = []

    for i, task in enumerate(tasks):
        context = pb.render(char_budget)
        output = generator.run(task, context)
        episode = Episode(
            task=task,
            context=context,
            output=output,
            reward=scorer(task, output),
            id=f"ep-{i}",
        )
        episodes.append(episode)
        pb.apply_all(cur.curate(reflector.reflect(episode, context), episode))

    return RunResult(playbook=pb, episodes=episodes)
