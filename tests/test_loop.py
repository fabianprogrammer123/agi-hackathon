from context_hub.loop import improve
from context_hub.playbook import Op
from context_hub.roles import DefaultCurator, Episode, Insight


class ContextReadingGenerator:
    """Succeeds only once the playbook has told it the magic word."""

    def run(self, task: str, context: str) -> str:
        return "correct" if "say correct" in context else "wrong"


class ScriptedReflector:
    def reflect(self, episode: Episode, context: str) -> list[Insight]:
        return [Insight(content="say correct", tags=("protocol",))]


def scorer(task: str, output: str) -> float:
    return 1.0 if output == "correct" else 0.0


def test_the_loop_actually_improves_across_episodes():
    class SucceedsOnceThenLearns(ContextReadingGenerator):
        pass

    class AlwaysTeaches:
        def reflect(self, episode: Episode, context: str) -> list[Insight]:
            # Seed the lesson on the first (failed) episode by reporting success upstream
            return [Insight(content="say correct")]

    result = improve(
        ["task-a", "task-b", "task-c"],
        generator=SucceedsOnceThenLearns(),
        reflector=AlwaysTeaches(),
        scorer=scorer,
        curator=_PermissiveCurator(),
    )
    rewards = [e.reward for e in result.episodes]
    assert rewards[0] == 0.0, "first episode has an empty playbook and must fail"
    assert rewards[-1] == 1.0, "later episodes should benefit from the learned context"
    assert result.mean_reward > 0


class _PermissiveCurator(DefaultCurator):
    """Admits lessons from failures too, so the test can bootstrap from a cold start."""

    def curate(self, insights, episode):
        from context_hub.playbook import Delta

        return [
            Delta(op=Op.ADD, content=i.content, tags=i.tags, episode=episode.id) for i in insights
        ]


def test_default_curator_ignores_lessons_from_failed_episodes():
    curator = DefaultCurator()
    failed = Episode(task="t", context="", output="wrong", reward=0.0, id="ep-0")
    deltas = curator.curate([Insight(content="a lesson")], failed)
    assert [d.op for d in deltas] == []


def test_default_curator_records_contradictions_even_on_failure():
    curator = DefaultCurator()
    failed = Episode(task="t", context="", output="wrong", reward=0.0, id="ep-0")
    deltas = curator.curate([Insight(content="x", contradicts=("abc",))], failed)
    assert [d.op for d in deltas] == [Op.DOWNVOTE]


def test_every_episode_is_recorded():
    result = improve(
        ["a", "b"],
        generator=ContextReadingGenerator(),
        reflector=ScriptedReflector(),
        scorer=scorer,
    )
    assert len(result.episodes) == 2
    assert [e.id for e in result.episodes] == ["ep-0", "ep-1"]
