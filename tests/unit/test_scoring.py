"""Barème d'AMC, question par question (BAR-01, SPEC.md §3)."""

from decimal import Decimal as D

import pytest

from bank.migrations._legacy_scoring import legacy_scoring
from bank.scoring import (
    Item,
    ScoringError,
    format_scoring,
    max_score,
    parse_number,
    parse_points,
    parse_scoring,
    plain,
    score,
)


def simple(chosen, scoring="", n=3, correct=0, points=None) -> D:
    item = Item(
        multiple=False,
        n_choices=n,
        correct=frozenset({correct}),
        scoring=parse_scoring(scoring),
        points=points or {},
    )
    return score(item, frozenset(chosen))


def multi(scoring="", n=4, correct=(0, 1), none=False) -> Item:
    """Question multiple de `n` propositions ; `none` : une de plus, « Aucune… », en dernier,
    juste si aucune autre ne l'est."""
    right = set(correct)
    if none and not right:
        right = {n}
    return Item(
        multiple=True,
        n_choices=n + 1 if none else n,
        correct=frozenset(right),
        scoring=parse_scoring(scoring),
        none=n if none else None,
    )


# --- Lecture du barème --------------------------------------------------------------------


def test_parse_scoring_reads_directives_in_order():
    assert parse_scoring("") == {}
    assert parse_scoring("  ") == {}
    assert parse_scoring("b=2, m=-0.5,v=.25") == {"b": D(2), "m": D("-0.5"), "v": D("0.25")}
    assert parse_scoring("haut=2,p=-1,MAX=3,e=-1,d=1,mz=2") == {
        "haut": D(2),
        "p": D(-1),
        "MAX": D(3),
        "e": D(-1),
        "d": D(1),
        "mz": D(2),
    }


def test_parse_scoring_ignores_empty_parts_like_amc():
    assert parse_scoring(",b=2,,m=-1, ") == {"b": D(2), "m": D(-1)}


def test_format_scoring_is_read_back_without_exponent():
    directives = parse_scoring("b=.0000001,m=-2.50")
    assert format_scoring(directives) == "b=0.0000001,m=-2.50"
    assert parse_scoring(format_scoring(directives)) == directives


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("P=4", "directive « P » non prise en charge"),
        ("formula=b", "directive « formula » non prise en charge"),
        ("max=2", "directive « max » non prise en charge"),  # MAX, en majuscules seulement
        ("b=2,b=3", "directive « b » répétée"),
        ("b", "« b » n'est pas de la forme directive=valeur"),
        ("b=deux", "valeur non numérique : « deux » pour « b »"),
        ("b=1,5", "« 5 » n'est pas de la forme directive=valeur"),  # virgule décimale
        ("b=1e3", "valeur non numérique : « 1e3 » pour « b »"),
    ],
)
def test_parse_scoring_refuses_with_a_reason(text, reason):
    with pytest.raises(ScoringError) as error:
        parse_scoring(text)
    assert str(error.value) == reason


def test_format_scoring_is_read_back():
    for text in ("", "b=2,m=-0.5", "haut=2", "mz=3,p=-1,MAX=3"):
        assert format_scoring(parse_scoring(text)) == text.replace(" ", "")
    assert format_scoring(parse_scoring(" b = 2 ,m=-.5")) == "b=2,m=-0.5"


@pytest.mark.parametrize("text", ["-2", "+1.5", "0", ".5", "999999.999", "-999999.999"])
def test_parse_points_accepts_what_the_field_stores(text):
    assert parse_points(text) == D(text)


@pytest.mark.parametrize("text", ["1000000", "-1000000", "0.0001", "deux", ""])
def test_parse_points_refuses_what_the_field_cannot_store(text):
    with pytest.raises(ScoringError):
        parse_points(text)


def test_parse_number():
    assert parse_number(" -0.5 ") == D("-0.5")
    with pytest.raises(ScoringError):
        parse_number("1,5")


def test_plain():
    assert str(plain(D("2.000"))) == "2"
    assert str(plain(D("-0.500"))) == "-0.5"
    assert str(plain(D("100"))) == "100"
    assert str(plain(D("-0"))) == "0"


# --- Question simple ----------------------------------------------------------------------


def test_simple_default_scoring():
    assert simple({0}) == 1
    assert simple({1}) == 0
    assert simple(set()) == 0


def test_simple_scoring_b_m_v():
    scoring = "b=2,m=-0.5,v=-0.25"
    assert simple({0}, scoring) == 2
    assert simple({2}, scoring) == D("-0.5")
    assert simple(set(), scoring) == D("-0.25")


def test_simple_several_choices_give_e():
    assert simple({0, 1}, "e=-3") == -3
    assert simple({0, 1}) == 0


def test_simple_mz_replaces_b_and_d_p_haut_have_no_effect():
    assert simple({0}, "b=2,mz=5") == 5
    assert simple({1}, "mz=5,m=-1") == -1
    assert simple({0}, "d=3,p=4,haut=7") == 1
    assert simple({1}, "m=-2,p=0") == -2  # pas de plancher pour une simple


def test_simple_choice_with_its_own_points():
    points = {1: D(-2), 0: D("0.5")}
    assert simple({1}, "b=3", points=points) == -2
    assert simple({0}, "b=3", points=points) == D("0.5")  # même juste : sa valeur
    assert simple({2}, "b=3,m=-1", points=points) == -1
    assert simple(set(), "v=-4", points=points) == -4


def test_simple_max():
    item = Item(multiple=False, n_choices=3, correct=frozenset({0}), scoring={"b": D(2)})
    assert max_score(item) == 2
    assert max_score(Item(False, 3, frozenset({0}), {"MAX": D(5)})) == 5


# --- Question multiple --------------------------------------------------------------------


def test_multiple_default_scoring_counts_well_treated_boxes():
    item = multi()  # A et B justes, sur 4
    assert score(item, frozenset({0, 1})) == 4
    assert score(item, frozenset({0})) == 3
    assert score(item, frozenset({0, 2})) == 2
    assert score(item, frozenset({2, 3})) == 0
    assert score(item, frozenset()) == 0
    assert max_score(item) == 4


def test_multiple_b_m_d_and_floor_p():
    item = multi("b=2,m=-1,d=1")
    assert score(item, frozenset({0, 1})) == 9  # 4 x 2 + 1
    assert score(item, frozenset({2, 3})) == -3  # 4 x -1 + 1
    floored = multi("b=1,m=-2,p=-1")
    assert score(floored, frozenset({2, 3})) == -1  # -8 relevé à p
    assert score(floored, frozenset({0, 1, 2})) == 1  # 3 - 2 = 1, au-dessus de p


def test_multiple_v_is_neither_shifted_nor_floored():
    assert score(multi("v=-3,p=-1,d=2"), frozenset()) == -3


def test_multiple_haut_example_of_the_spec():
    item = multi("haut=2")  # 4 propositions : d = 2 - 4, plancher 0
    assert score(item, frozenset({0, 1})) == 2
    assert score(item, frozenset({0})) == 1
    assert score(item, frozenset({0, 2})) == 0
    assert score(item, frozenset({2, 3})) == 0
    assert max_score(item) == 2
    assert score(multi("haut=2,p=-5"), frozenset({2, 3})) == -2  # p donné : il remplace 0


def test_multiple_mz_all_or_floor():
    item = multi("mz=3")
    assert score(item, frozenset({0, 1})) == 3
    assert score(item, frozenset({0})) == 0  # p = 0 par défaut
    assert score(multi("mz=3,p=-1"), frozenset({0})) == -1
    assert score(multi("mz=3,p=-5"), frozenset({0})) == -5  # m = -(3 + 5 + 1), plancher -5
    assert max_score(item) == 3


def test_multiple_zero_haut_or_mz_are_ignored():
    assert score(multi("haut=0"), frozenset({0, 1})) == 4
    assert score(multi("mz=0"), frozenset({0})) == 3


def test_multiple_max_directive():
    assert max_score(multi("MAX=10")) == 10


def test_none_of_these_is_out_of_the_sum():
    item = multi(n=3, correct=(0,), none=True)  # A juste ; D = « Aucune… »
    assert score(item, frozenset({0})) == 3
    assert score(item, frozenset({3})) == 2  # A non cochée : mal traitée
    assert score(item, frozenset({0, 3})) == 0  # « Aucune » combinée : e
    assert score(multi("e=-2", n=3, none=True), frozenset({1, 3})) == -2


def test_none_of_these_when_nothing_else_is_right():
    item = multi(n=3, correct=(), none=True)
    assert score(item, frozenset({3})) == 3
    assert score(item, frozenset({0})) == 2
    assert max_score(item) == 3
    assert max_score(multi("haut=2", n=3, correct=(), none=True)) == 2


def test_answer_outside_the_choices_is_refused():
    with pytest.raises(ValueError, match="hors des propositions"):
        score(multi(), frozenset({4}))


# --- Barème des QCM d'avant I12 (migrations) ----------------------------------------------


def legacy(multiple=False, n=3, b="1", m="0", v="0", p=None) -> str:
    return legacy_scoring(
        multiple=multiple, n_choices=n, b=D(b), m=D(m), v=D(v), p=None if p is None else D(p)
    )


def test_legacy_scoring_omits_base_values():
    assert legacy() == ""
    assert legacy(b="2.00", m="-0.50", v="0") == "b=2,m=-0.5"
    assert legacy(multiple=True, p="0") == "p=0"
    assert legacy(p="-1") == ""  # pas de plancher pour une simple


def test_legacy_scoring_keeps_the_old_maximum_when_the_floor_is_above():
    assert legacy(multiple=True, n=3, b="1", p="5") == "p=5,MAX=3"
    assert legacy(multiple=True, n=3, b="1", p="3") == "p=3"


@pytest.mark.parametrize(
    ("b", "m", "v", "p"),
    [("1", "0", "0", None), ("2", "-0.5", "-0.25", None), ("0.5", "-1", "-1", "-2")],
)
def test_legacy_scoring_gives_the_same_marks(b, m, v, p):
    """Avant I12 : simple b/m/v ; multiple, b ou m par case, plancher p, v si rien."""
    for chosen in (set(), {0}, {1}, {0, 1}, {1, 2}, {0, 1, 2}):
        right = frozenset({0, 1})
        boxes = sum(D(b) if (i in chosen) == (i in right) else D(m) for i in range(3))
        old = D(v) if not chosen else boxes if p is None else max(boxes, D(p))
        item = Item(True, 3, right, parse_scoring(legacy(True, 3, b, m, v, p)))
        assert score(item, frozenset(chosen)) == old
    old_simple = {0: D(b), 1: D(m)}
    for index, expected in old_simple.items():
        item = Item(False, 3, frozenset({0}), parse_scoring(legacy(False, 3, b, m, v, p)))
        assert score(item, frozenset({index})) == expected
