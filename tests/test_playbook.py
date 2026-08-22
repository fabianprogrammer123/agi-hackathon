from context_hub.playbook import MIN_VOTES_TO_RETIRE, Delta, Op, Playbook


def add(pb: Playbook, content: str, **kw) -> str:
    return pb.apply(Delta(op=Op.ADD, content=content, **kw)).id


def test_add_creates_entry():
    pb = Playbook()
    entry_id = add(pb, "Check the schema before writing SQL.")
    assert pb.entries[entry_id].content == "Check the schema before writing SQL."
    assert len(pb.active()) == 1


def test_rediscovering_a_lesson_upvotes_instead_of_duplicating():
    pb = Playbook()
    first = add(pb, "Check the schema before writing SQL.", episode="ep-0")
    second = add(pb, "  check   THE schema before writing SQL.  ", episode="ep-1")
    assert first == second
    assert len(pb.active()) == 1
    assert pb.entries[first].helpful == 1
    assert pb.entries[first].provenance == ("ep-0", "ep-1")


def test_confidence_is_smoothed_so_one_lucky_hit_does_not_outrank_evidence():
    pb = Playbook()
    lucky = add(pb, "lucky guess")
    proven = add(pb, "proven rule")
    for _ in range(40):
        pb.apply(Delta(op=Op.UPVOTE, entry_id=proven))
    pb.apply(Delta(op=Op.DOWNVOTE, entry_id=proven))
    assert pb.active()[0].id == proven
    assert pb.entries[proven].confidence > pb.entries[lucky].confidence


def test_entry_retires_once_evidence_turns_against_it():
    pb = Playbook()
    entry_id = add(pb, "Always retry twice on any error.")
    for _ in range(MIN_VOTES_TO_RETIRE):
        pb.apply(Delta(op=Op.DOWNVOTE, entry_id=entry_id))
    assert pb.entries[entry_id].retired
    assert pb.active() == []


def test_a_single_downvote_does_not_retire():
    pb = Playbook()
    entry_id = add(pb, "Always retry twice on any error.")
    pb.apply(Delta(op=Op.DOWNVOTE, entry_id=entry_id))
    assert not pb.entries[entry_id].retired


def test_rediscovery_revives_a_retired_lesson():
    pb = Playbook()
    entry_id = add(pb, "Prefer batched writes.")
    for _ in range(MIN_VOTES_TO_RETIRE):
        pb.apply(Delta(op=Op.DOWNVOTE, entry_id=entry_id))
    assert pb.entries[entry_id].retired
    add(pb, "Prefer batched writes.")
    assert not pb.entries[entry_id].retired


def test_revision_supersedes_rather_than_erases():
    pb = Playbook()
    old = add(pb, "Retry on error.")
    new = pb.apply(Delta(op=Op.REVISE, entry_id=old, content="Retry only on 5xx errors.")).id
    assert pb.entries[old].retired
    assert not pb.entries[new].retired
    assert len(pb.active()) == 1


def test_votes_on_unknown_entries_are_ignored_not_fatal():
    pb = Playbook()
    assert pb.apply(Delta(op=Op.UPVOTE, entry_id="nope")) is None


def test_render_drops_whole_entries_at_the_budget():
    pb = Playbook()
    for i in range(20):
        add(pb, f"Lesson number {i} about long-running agents.")
    rendered = pb.render(char_budget=200)
    assert len(rendered) <= 200
    assert all(line.startswith("- ") for line in rendered.splitlines())


def test_render_is_ranked_by_confidence():
    pb = Playbook()
    weak = add(pb, "weak lesson")
    strong = add(pb, "strong lesson")
    for _ in range(5):
        pb.apply(Delta(op=Op.UPVOTE, entry_id=strong))
    pb.apply(Delta(op=Op.DOWNVOTE, entry_id=weak))
    assert pb.render().splitlines()[0].startswith("- strong lesson")


def test_replay_reconstructs_a_past_belief_state():
    pb = Playbook()
    add(pb, "First lesson.")
    checkpoint = pb.tick
    add(pb, "Second lesson.")
    assert len(pb.at(checkpoint).active()) == 1
    assert len(pb.active()) == 2


def test_journal_roundtrips_through_disk(tmp_path):
    pb = Playbook()
    entry_id = add(pb, "Persisted lesson.", episode="ep-0")
    pb.apply(Delta(op=Op.UPVOTE, entry_id=entry_id, episode="ep-1"))

    path = tmp_path / "playbook.json"
    pb.save(path)
    restored = Playbook.load(path)

    assert restored.render() == pb.render()
    assert restored.tick == pb.tick
