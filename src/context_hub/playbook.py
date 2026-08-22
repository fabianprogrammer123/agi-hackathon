"""The playbook: a curated, auditable set of lessons an agent has learned.

The design goal is not storage -- it is *curation under contradiction*. Anything can
append to a memory store; the hard part is deciding what to keep, what to retire, and
being able to show that the context got better rather than merely bigger.

Three properties make that possible here:

1. Entries are only ever changed through a :class:`Delta`. There is no path that
   rewrites the whole playbook, which is what causes context collapse.
2. Every entry carries provenance and a helpful/harmful tally, so promotion and
   demotion are evidence-driven rather than vibes.
3. Every mutation is journalled against a logical clock, so the playbook's belief
   state at any past tick can be replayed and diffed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

# An entry needs this many harmful votes before retirement is even considered. Below
# it, a single unlucky episode could evict a good lesson.
MIN_VOTES_TO_RETIRE = 3

# Confidence at or below which a sufficiently-voted entry is retired.
RETIRE_BELOW = 0.34


def _fingerprint(content: str) -> str:
    """Content hash used for dedup, insensitive to whitespace and casing."""
    normalized = re.sub(r"\s+", " ", content).strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


class Op(str, Enum):
    """The only ways a playbook may change."""

    ADD = "add"
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"
    REVISE = "revise"
    RETIRE = "retire"


@dataclass(frozen=True)
class Entry:
    """One lesson. Immutable -- edits produce a new Entry via :meth:`dataclasses.replace`."""

    id: str
    content: str
    tags: tuple[str, ...] = ()
    helpful: int = 0
    harmful: int = 0
    provenance: tuple[str, ...] = ()
    created_at: int = 0
    updated_at: int = 0
    retired_at: int | None = None

    @property
    def votes(self) -> int:
        return self.helpful + self.harmful

    @property
    def confidence(self) -> float:
        """Laplace-smoothed success rate.

        Smoothing matters: a raw ratio ranks a 1/1 entry above a 40/2 entry, which
        would let a single lucky episode outrank a well-evidenced lesson.
        """
        return (self.helpful + 1) / (self.votes + 2)

    @property
    def retired(self) -> bool:
        return self.retired_at is not None

    def should_retire(self) -> bool:
        return (
            not self.retired
            and self.votes >= MIN_VOTES_TO_RETIRE
            and self.confidence <= RETIRE_BELOW
        )


@dataclass(frozen=True)
class Delta:
    """A single proposed change, emitted by the Curator.

    Deltas are the audit unit. A run's whole learning history is its list of deltas,
    and replaying a prefix of that list reconstructs the playbook at any past tick.
    """

    op: Op
    content: str = ""
    entry_id: str | None = None
    tags: tuple[str, ...] = ()
    episode: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "op": self.op.value,
            "content": self.content,
            "entry_id": self.entry_id,
            "tags": list(self.tags),
            "episode": self.episode,
            "reason": self.reason,
        }


@dataclass
class Playbook:
    """An append-only-journalled, delta-updated set of lessons."""

    entries: dict[str, Entry] = field(default_factory=dict)
    journal: list[tuple[int, Delta]] = field(default_factory=list)
    tick: int = 0

    # -- mutation ---------------------------------------------------------------

    def apply(self, delta: Delta) -> Entry | None:
        """Apply one delta and journal it. Returns the affected entry, if any."""
        self.tick += 1
        self.journal.append((self.tick, delta))

        handlers = {
            Op.ADD: self._add,
            Op.UPVOTE: lambda d: self._vote(d, helpful=True),
            Op.DOWNVOTE: lambda d: self._vote(d, helpful=False),
            Op.REVISE: self._revise,
            Op.RETIRE: self._retire,
        }
        return handlers[delta.op](delta)

    def apply_all(self, deltas: list[Delta]) -> list[Entry | None]:
        return [self.apply(d) for d in deltas]

    def _add(self, delta: Delta) -> Entry:
        entry_id = _fingerprint(delta.content)
        existing = self.entries.get(entry_id)

        # Dedup: re-deriving a lesson you already hold is evidence for it, not a new
        # lesson. Collapsing it into an upvote is what keeps the playbook from
        # bloating with near-identical restatements over a long run.
        if existing is not None:
            merged = replace(
                existing,
                helpful=existing.helpful + 1,
                tags=tuple(dict.fromkeys(existing.tags + delta.tags)),
                provenance=existing.provenance + ((delta.episode,) if delta.episode else ()),
                updated_at=self.tick,
                retired_at=None,  # independent rediscovery revives a retired lesson
            )
            self.entries[entry_id] = merged
            return merged

        entry = Entry(
            id=entry_id,
            content=delta.content.strip(),
            tags=delta.tags,
            provenance=(delta.episode,) if delta.episode else (),
            created_at=self.tick,
            updated_at=self.tick,
        )
        self.entries[entry_id] = entry
        return entry

    def _vote(self, delta: Delta, *, helpful: bool) -> Entry | None:
        entry = self.entries.get(delta.entry_id or "")
        if entry is None:
            return None
        updated = replace(
            entry,
            helpful=entry.helpful + (1 if helpful else 0),
            harmful=entry.harmful + (0 if helpful else 1),
            provenance=entry.provenance + ((delta.episode,) if delta.episode else ()),
            updated_at=self.tick,
        )
        if updated.should_retire():
            updated = replace(updated, retired_at=self.tick)
        self.entries[updated.id] = updated
        return updated

    def _revise(self, delta: Delta) -> Entry | None:
        old = self.entries.get(delta.entry_id or "")
        if old is None:
            return None
        new_id = _fingerprint(delta.content)
        if new_id == old.id:
            return old
        # A revision supersedes rather than erases: the old entry is retired so the
        # journal still explains why the wording changed.
        self.entries[old.id] = replace(old, retired_at=self.tick, updated_at=self.tick)
        revised = Entry(
            id=new_id,
            content=delta.content.strip(),
            tags=tuple(dict.fromkeys(old.tags + delta.tags)),
            helpful=old.helpful,
            harmful=old.harmful,
            provenance=old.provenance + ((delta.episode,) if delta.episode else ()),
            created_at=self.tick,
            updated_at=self.tick,
        )
        self.entries[new_id] = revised
        return revised

    def _retire(self, delta: Delta) -> Entry | None:
        entry = self.entries.get(delta.entry_id or "")
        if entry is None or entry.retired:
            return entry
        retired = replace(entry, retired_at=self.tick, updated_at=self.tick)
        self.entries[retired.id] = retired
        return retired

    # -- reading ----------------------------------------------------------------

    def active(self) -> list[Entry]:
        """Live entries, best-evidenced first."""
        live = [e for e in self.entries.values() if not e.retired]
        return sorted(live, key=lambda e: (-e.confidence, -e.votes, e.created_at))

    def render(self, char_budget: int = 4000) -> str:
        """Compile the playbook into context text, highest-confidence entries first.

        The budget is what makes this a *hub* rather than a log: a long-running agent
        cannot carry everything it has learned, so ranking decides what it walks in
        with. Entries are dropped whole -- a truncated lesson is worse than none.
        """
        lines: list[str] = []
        used = 0
        for entry in self.active():
            tags = f" [{', '.join(entry.tags)}]" if entry.tags else ""
            line = f"- {entry.content}{tags} (conf {entry.confidence:.2f}, n={entry.votes})"
            if used + len(line) + 1 > char_budget:
                break
            lines.append(line)
            used += len(line) + 1
        return "\n".join(lines)

    def at(self, tick: int) -> Playbook:
        """Replay the journal up to ``tick`` and return the playbook as it was then.

        This is the audit story: you can diff ``pb.at(10).render()`` against
        ``pb.at(50).render()`` and show precisely what the agent learned in between.
        """
        past = Playbook()
        for t, delta in self.journal:
            if t > tick:
                break
            past.apply(delta)
        return past

    # -- persistence ------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Persist the journal. The journal is the source of truth; entries derive from it."""
        payload = {"tick": self.tick, "journal": [[t, d.to_dict()] for t, d in self.journal]}
        Path(path).write_text(json.dumps(payload, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> Playbook:
        payload = json.loads(Path(path).read_text())
        pb = cls()
        for _, raw in payload["journal"]:
            pb.apply(
                Delta(
                    op=Op(raw["op"]),
                    content=raw["content"],
                    entry_id=raw["entry_id"],
                    tags=tuple(raw["tags"]),
                    episode=raw["episode"],
                    reason=raw["reason"],
                )
            )
        return pb
