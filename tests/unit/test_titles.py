"""Ordre des titres de QCM (BAN-03, SES-01) : sans majuscules ni accents."""

from bank.models import Quiz, by_title, title_key


def test_title_key_ignores_case_and_accents():
    titles = ["Zoologie", "algèbre", "Écologie", "Biologie", "Ecologie", "école"]
    assert sorted(titles, key=title_key) == [
        "algèbre",
        "Biologie",
        "école",
        "Ecologie",
        "Écologie",
        "Zoologie",
    ]


def test_by_title_breaks_ties_by_creation_order():
    quizzes = [Quiz(pk=3, title="Partiel"), Quiz(pk=1, title="Partiel"), Quiz(pk=2, title="Bilan")]
    assert [q.pk for q in by_title(quizzes)] == [2, 1, 3]
