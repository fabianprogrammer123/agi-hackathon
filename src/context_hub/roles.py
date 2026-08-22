"""The three roles of the improvement loop.

Named after the ACE framework (Agentic Context Engineering, arXiv:2510.04618): a
Generator that acts, a Reflector that judges, and a Curator that decides what the
playbook should become. Keeping them separate is what stops the loop from marking
its own homework.

Each is a Protocol, so a real LLM-backed implementation and a deterministic test
double are interchangeable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from context_hub.playbook import Delta, Op


@dataclass(frozen=True)
class Episode:
    """One attempt at a task, and how it went."""

    task: str
    context: str
    output: str
    reward: float
    id: str = ""

    @property
    def succeeded(self) -> bool:
        return self.reward >= 0.5


@dataclass(frozen=True)
class Insight:
    """A lesson the Reflector extracted, before the Curator decides what to do with it."""

    content: str
    supports: tuple[str, ...] = ()  # entry ids this episode vindicated
    contradicts: tuple[str, ...] = ()  # entry ids this episode undermined
    tags: tuple[str, ...] = ()


class Generator(Protocol):
    """Attempts the task, given the compiled playbook as context."""

    def run(self, task: str, context: str) -> str: ...


class Reflector(Protocol):
    """Distils an episode into insights. Must not touch the playbook itself."""

    def reflect(self, episode: Episode, context: str) -> list[Insight]: ...


class Curator(Protocol):
    """Turns insights into deltas. The only component allowed to change the playbook."""

    def curate(self, insights: list[Insight], episode: Episode) -> list[Delta]: ...


class DefaultCurator:
    """A deterministic curator that needs no model.

    Deliberately conservative: it converts explicit support and contradiction into
    votes, and only admits a new entry when the episode actually succeeded. Lessons
    learned from failure are the most tempting and the least reliable -- an agent
    that failed usually cannot tell you why.
    """

    def curate(self, insights: list[Insight], episode: Episode) -> list[Delta]:
        deltas: list[Delta] = []
        for insight in insights:
            for entry_id in insight.supports:
                deltas.append(Delta(op=Op.UPVOTE, entry_id=entry_id, episode=episode.id))
            for entry_id in insight.contradicts:
                deltas.append(Delta(op=Op.DOWNVOTE, entry_id=entry_id, episode=episode.id))
            if episode.succeeded and insight.content:
                deltas.append(
                    Delta(
                        op=Op.ADD,
                        content=insight.content,
                        tags=insight.tags,
                        episode=episode.id,
                        reason=f"reward={episode.reward:.2f}",
                    )
                )
        return deltas
