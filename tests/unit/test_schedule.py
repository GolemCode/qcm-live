"""Déroulement d'une session : groupes, créneaux, rotation, mélange (fonctions pures)."""

import itertools

import pytest

from live.schedule import Schedule, shuffled


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


def test_session_ends_after_last_slot():
    assert Schedule(5, 2, 30).position(150) is None


@pytest.mark.parametrize(("n_questions", "shown"), itertools.product(range(1, 8), range(1, 7)))
def test_rotation_every_student_answers_every_question_once(n_questions, shown):
    schedule = Schedule(n_questions, shown, 10)
    for rank in range(8):
        seen = [schedule.question_for(slot, rank) for slot in schedule.slots]
        assert sorted(seen) == list(range(n_questions))
        for slot in schedule.slots:  # la couleur est le rang de la question dans son groupe
            question = schedule.question_for(slot, rank)
            assert schedule.groups[slot.group][schedule.color_for(slot, rank) - 1] == question


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
