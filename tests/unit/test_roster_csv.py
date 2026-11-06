"""Lecture du CSV d'un groupe (SPEC.md §2 bis) : tous les cas, sur une fonction pure."""

import pytest
from roster.csv_import import MAX_BYTES, Entry, RosterError, parse_roster


def errors_of(data: bytes) -> list[str]:
    with pytest.raises(RosterError) as excinfo:
        parse_roster(data)
    return excinfo.value.messages


def test_semicolon_with_header_and_blank_lines():
    data = b"numero;nom\n\n00123;DURAND Elise\n42;MARTIN Leo\n"
    assert parse_roster(data) == [Entry("00123", "DURAND Elise"), Entry("42", "MARTIN Leo")]


def test_comma_with_quotes_and_no_header():
    data = b'1,"DUPONT, Jeanne"\n2,ROUX Paul\n'
    assert parse_roster(data) == [Entry("1", "DUPONT, Jeanne"), Entry("2", "ROUX Paul")]


def test_semicolon_wins_when_present_in_first_line():
    assert parse_roster(b"1;Dupont, Jean\n") == [Entry("1", "Dupont, Jean")]


@pytest.mark.parametrize(
    "data",
    [
        "1;Élise\n".encode(),
        "﻿1;Élise\n".encode(),
        "1;Élise\r\n".encode("cp1252"),
    ],
)
def test_encodings(data):
    assert parse_roster(data) == [Entry("1", "Élise")]


def test_spaces_and_trailing_empty_columns_are_ignored():
    assert parse_roster(b" 7 ; Ng Anh ;;\n") == [Entry("7", "Ng Anh")]


def test_header_requires_two_filled_cells_without_digit_in_first():
    # « ;B » n'est pas un en-tête : c'est une ligne au numéro vide.
    assert errors_of(b";B\n1;A\n") == ["Ligne 1 : numéro vide."]
    # « 12a;B » contient un chiffre : ligne de données invalide, pas un en-tête.
    assert "Ligne 1" in errors_of(b"12a;B\n1;A\n")[0]
    # Seule la première ligne non vide peut être un en-tête.
    assert "Ligne 3" in errors_of(b"numero;nom\n1;A\nnumero;nom\n")[0]


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"1;A\n2\n", "Ligne 2 : format incorrect"),
        (b"1;A;B\n", "Ligne 1 : format incorrect"),
        (b"1;A\n2;B\n1;C\n", "Ligne 3 : numéro 1 en double (déjà ligne 1)."),
        (b"1;A\n;B\n", "Ligne 2 : numéro vide."),
        (b"1;A\n2;\n", "Ligne 2 : nom vide."),
        (b"1;A\n2x;B\n", "Ligne 2 : le numéro « 2x » ne doit contenir que des chiffres"),
        (b"1;A\n" + b"1" * 21 + b";B\n", "Ligne 2 : le numéro"),
        (b"1;" + b"A" * 201 + b"\n", "Ligne 1 : nom trop long"),
    ],
)
def test_line_errors(data, expected):
    assert errors_of(data)[0].startswith(expected)


def test_all_faulty_lines_are_reported_in_order():
    assert [m.split(" :")[0] for m in errors_of(b"1;A\n2\n;C\n4;\n")] == [
        "Ligne 2",
        "Ligne 3",
        "Ligne 4",
    ]


def test_error_list_is_capped():
    messages = errors_of(b"".join(b"x;A\n" for _ in range(30)))
    assert len(messages) == 21
    assert messages[-1] == "… et 10 autres erreurs."


@pytest.mark.parametrize("data", [b"", b"\n\n", b"numero;nom\n"])
def test_no_student(data):
    assert errors_of(data) == ["Le fichier ne contient aucun étudiant."]


def test_too_large():
    assert "trop volumineux" in errors_of(b"1;A\n" * (MAX_BYTES // 4 + 1))[0]


def test_unreadable_encoding():
    assert "encodage" in errors_of(b"1;\x81\x8d\n")[0]
