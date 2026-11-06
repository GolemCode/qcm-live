"""Barème AMC (b, m, v, p) : tous les cas, sur des fonctions pures."""

from decimal import Decimal as D

import pytest

from bank.scoring import Scale, max_score, score

CORRECT_0 = frozenset({0})
DEFAULT = Scale()


def simple(chosen, scale=DEFAULT, n=3, correct=CORRECT_0):
    return score(
        multiple=False, n_choices=n, correct=correct, chosen=frozenset(chosen), scale=scale
    )


def multiple(chosen, correct, scale=DEFAULT, n=4):
    return score(
        multiple=True,
        n_choices=n,
        correct=frozenset(correct),
        chosen=frozenset(chosen),
        scale=scale,
    )


def test_amc_defaults():
    assert Scale() == Scale(b=D(1), m=D(0), v=D(0), p=None)


SIMPLE_SCALE = Scale(b=D(2), m=D("-0.5"), v=D("-0.25"))


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [((), D("-0.25")), ((0,), D(2)), ((1,), D("-0.5")), ((2,), D("-0.5"))],
)
def test_simple_question(chosen, expected):
    assert simple(chosen, SIMPLE_SCALE) == expected


def test_simple_question_with_defaults():
    assert simple((0,)) == 1
    assert simple((1,)) == 0
    assert simple(()) == 0


def test_simple_question_rejects_several_answers():
    with pytest.raises(ValueError, match="une seule"):
        simple((0, 1))


def test_answer_outside_choices_is_rejected():
    with pytest.raises(ValueError, match="hors"):
        simple((3,))
    with pytest.raises(ValueError, match="hors"):
        multiple((4,), correct=(0,))


MULTI_SCALE = Scale(b=D(2), m=D("-0.5"), v=D(-1))


@pytest.mark.parametrize(
    ("chosen", "expected"),
    [
        # 4 propositions, justes = {0, 1}.
        ((0, 1), D(8)),  # tout bien traité : 4 fois b
        ((0,), D("5.5")),  # 1 juste oubliée : 3 b + 1 m
        ((0, 1, 2), D("5.5")),  # 1 fausse cochée
        ((2, 3), D(-2)),  # tout mal traité : 4 fois m
        ((), D(-1)),  # rien coché : v
    ],
)
def test_multiple_question(chosen, expected):
    assert multiple(chosen, correct=(0, 1), scale=MULTI_SCALE) == expected


def test_multiple_question_floor_applies_to_sum_only():
    floored = Scale(b=D(1), m=D(-2), v=D(-3), p=D(-1))
    assert multiple((2, 3), correct=(0, 1), scale=floored) == D(-1)  # somme -8 relevée à p
    assert multiple((0, 1, 2), correct=(0, 1), scale=floored) == D(1)  # 3 - 2 = 1 > p
    assert multiple((), correct=(0, 1), scale=floored) == D(-3)  # v, non borné par p


def test_multiple_question_floor_zero():
    assert multiple((2,), correct=(0,), scale=Scale(m=D(-5), p=D(0))) == 0


def test_max_score():
    assert max_score(multiple=False, n_choices=5, scale=SIMPLE_SCALE) == D(2)
    assert max_score(multiple=True, n_choices=4, scale=MULTI_SCALE) == D(8)


def test_scale_to_json_keeps_decimals_exactly():
    scale = Scale(b=D("0.5"), m=D("-0.25"), v=D("-1"), p=D("-2.00"))
    assert scale.to_json() == {"b": "0.5", "m": "-0.25", "v": "-1", "p": "-2.00"}
    assert Scale().to_json() == {"b": "1", "m": "0", "v": "0", "p": None}
