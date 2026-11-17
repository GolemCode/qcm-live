"""Déroulement d'une session : groupes, créneaux, rotation, mélange (fonctions pures)."""

import itertools

import pytest

from live.schedule import Schedule, seconds_to_remove, shuffled


def test_groups_of_n_in_quiz_order_last_one_smaller():
    assert Schedule(5, 2, 30).groups == [[0, 1], [2, 3], [4]]
    assert Schedule(3, 6, 30).groups == [[0, 1, 2]]
    assert Schedule(4, 1, 30).groups == [[0], [1], [2], [3]]


def test_one_slot_per_question():
    schedule = Schedule(5, 2, 30)
    assert [(s.group, s.step, s.size) for s in schedule.slots] == [
        (0, 0, 2),
        (0, 1, 2),
        (1, 0, 2),
        (1, 1, 2),
        (2, 0, 1),
    ]
    assert schedule.duration == 150


@pytest.mark.parametrize(
    ("elapsed", "slot", "remaining"),
    [(-3, 0, 30), (0, 0, 30), (29.5, 0, 0.5), (30, 1, 30), (61, 2, 29), (149.9, 4, 0.1)],
)
def test_position(elapsed, slot, remaining):
    position = Schedule(5, 2, 30).position(elapsed)
    assert position is not None
    assert position.slot.index == slot
    assert position.remaining == pytest.approx(remaining)
    assert position.length == 30


def test_session_ends_after_last_slot():
    assert Schedule(5, 2, 30).position(150) is None


@pytest.mark.parametrize(
    ("elapsed", "slot", "remaining"),
    [
        (29.5, 0, 0.5),
        (30, 1, 50),  # créneau 1 : 30 + 20 s ajoutées
        (59.5, 1, 20.5),
        (79.9, 1, 0.1),
        (80, 2, 30),  # les suivants sont décalés de 20 s
        (110, 3, 40),  # créneau 3 : 30 + 10 s
        (149.5, 3, 0.5),
        (150, 4, 30),
        (179.5, 4, 0.5),
    ],
)
def test_added_time_lengthens_its_slot_and_shifts_the_next(elapsed, slot, remaining):
    schedule = Schedule(5, 2, 30, extra={1: 20, 3: 10})
    assert schedule.deadlines == [30, 80, 110, 150, 180]
    assert schedule.duration == 180
    position = schedule.position(elapsed)
    assert position is not None
    assert position.slot.index == slot
    assert position.remaining == pytest.approx(remaining)
    assert position.length == 30 + schedule.extra.get(slot, 0)
    assert schedule.position(180) is None


@pytest.mark.parametrize(
    ("remaining", "removed"),
    [(30, 25), (20, 15), (19.2, 15), (6, 1), (5.01, 1), (5, 0), (4.5, 0), (0.1, 0)],
)
def test_seconds_to_remove_leaves_5_s_at_most(remaining, removed):
    """TPS-02 : il reste 5 s au plus, et un peu moins quand le temps restant n'est pas entier ;
    jamais de temps ajouté quand il en reste déjà 5 ou moins."""
    assert seconds_to_remove(remaining) == removed
    assert remaining - removed <= 5
    assert removed == 0 or remaining - removed > 4


def test_removed_time_ends_the_slot_and_brings_the_next_forward():
    """TPS-02 : 15 s retirées au créneau 1 (secondes négatives), puis 10 rajoutées (TPS-01)."""
    schedule = Schedule(3, 1, 30, extra={1: -15 + 10})
    assert schedule.deadlines == [30, 55, 85]
    position = schedule.position(50)
    assert position is not None
    assert (position.slot.index, position.remaining, position.length) == (1, 5, 25)
    last = Schedule(1, 1, 30, extra={0: -20})
    assert last.duration == 10
    assert last.position(10) is None


def test_added_time_changes_neither_slots_nor_rotation():
    plain, extended = Schedule(5, 2, 30), Schedule(5, 2, 30, extra={0: 10, 4: 50})
    assert extended.slots == plain.slots
    for slot in plain.slots:
        for rank in range(4):
            assert extended.question_for(slot, rank) == plain.question_for(slot, rank)


@pytest.mark.parametrize(
    ("n_questions", "shown"), list(itertools.product(range(1, 8), range(1, 7)))
)
def test_rotation_every_student_answers_every_question_once(n_questions, shown):
    schedule = Schedule(n_questions, shown, 10)
    for rank in range(8):
        seen = [schedule.question_for(slot, rank) for slot in schedule.slots]
        assert sorted(seen) == list(range(n_questions))
        for slot in schedule.slots:  # la couleur est le rang de la question dans son groupe
            question = schedule.question_for(slot, rank)
            assert schedule.groups[slot.group][slot.color(rank) - 1] == question


@pytest.mark.parametrize("shown", range(2, 7))
def test_rotation_neighbours_never_share_a_question(shown):
    schedule = Schedule(shown, shown, 10)
    for slot in schedule.slots:
        questions = [schedule.question_for(slot, rank) for rank in range(shown)]
        assert len(set(questions)) == shown


def test_n1_same_order_for_everyone():
    schedule = Schedule(3, 1, 10)
    orders = {tuple(schedule.question_for(s, rank) for s in schedule.slots) for rank in range(5)}
    assert orders == {(0, 1, 2)}


def test_shuffle_is_a_stable_permutation_specific_to_the_seed():
    order = shuffled(6, "abc:0")
    assert sorted(order) == list(range(6))
    assert shuffled(6, "abc:0") == order
    assert len({tuple(shuffled(6, f"student-{i}:0")) for i in range(20)}) > 1
