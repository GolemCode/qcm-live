"""Lecture du CSV d'un groupe (SPEC.md §2 bis) : tous les cas, sur une fonction pure."""

import pytest

from roster.csv_import import MAX_BYTES, Entry, RosterError, parse_roster


def errors_of(data: bytes) -> list[str]:
    with pytest.raises(RosterError) as excinfo:
        parse_roster(data)
    return excinfo.value.messages


def test_semicolon_with_header_and_blank_lines():
    data = b"numero;nom\n\n00123;DURAND Elise\n42;MARTIN Leo\n"
    assert parse_roster(data).entries == [Entry("00123", "DURAND Elise"), Entry("42", "MARTIN Leo")]


def test_comma_with_quotes_and_no_header():
    data = b'1,"DUPONT, Jeanne"\n2,ROUX Paul\n'
    assert parse_roster(data).entries == [Entry("1", "DUPONT, Jeanne"), Entry("2", "ROUX Paul")]


def test_semicolon_wins_when_present_in_first_line():
    assert parse_roster(b"1;Dupont, Jean\n").entries == [Entry("1", "Dupont, Jean")]


@pytest.mark.parametrize(
    "data",
    [
        "1;Élise\n".encode(),
        "﻿1;Élise\n".encode(),
        "1;Élise\r\n".encode("cp1252"),
    ],
)
def test_encodings(data):
    assert parse_roster(data).entries == [Entry("1", "Élise")]


def test_spaces_and_trailing_empty_columns_are_ignored():
    assert parse_roster(b" 7 ; Ng Anh ;;\n;;\n").entries == [Entry("7", "Ng Anh")]


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
    # « 1x » contient un chiffre : la première ligne n'est pas prise pour un en-tête.
    messages = errors_of(b"".join(b"1x;A\n" for _ in range(30)))
    assert len(messages) == 21
    assert messages[-1] == "… et 10 autres erreurs."


@pytest.mark.parametrize("data", [b"", b"\n\n", b"numero;nom\n"])
def test_no_student(data):
    assert errors_of(data) == ["Le fichier ne contient aucun étudiant."]


def test_too_large():
    assert "trop volumineux" in errors_of(b"1;A\n" * (MAX_BYTES // 4 + 1))[0]


def test_unreadable_encoding():
    assert "encodage" in errors_of(b"1;\x81\x8d\n")[0]


def test_header_is_reported():
    assert parse_roster(b"\nnumero;nom\n1;A\n").header == (2, "numero ; nom")
    assert parse_roster(b"1;A\n").header is None


@pytest.mark.parametrize("number", ["\uff11\uff12\uff13", "\u0661\u0662\u0663"])
def test_only_ascii_digits(number):
    assert "chiffres" in errors_of(f"1;A\n{number};B\n".encode())[0]


def test_utf16_is_refused_with_encoding_message():
    assert "encodage" in errors_of("numero;nom\n1;DURAND\n".encode("utf-16"))[0]


def test_oversized_field_is_a_format_error_not_a_crash():
    assert errors_of(b"1;A\n2;" + b"x" * 200_000 + b"\n")[0].startswith("Ligne 2 : format")


def test_line_numbers_follow_file_lines_only():
    # \x0c (saut de page) ou U+2028 dans un nom ne coupent pas la ligne.
    data = "1;A\x0cB\n2;C\u2028D\n3;\n".encode()
    assert errors_of(data)[-1] == "Ligne 3 : nom vide."


def test_quoted_multiline_field_reports_its_first_line():
    assert errors_of(b'1;a\n"2;b\n3;c"\n')[0].startswith("Ligne 2 :")


def test_control_characters_in_name_are_refused():
    assert errors_of(b"1;a\x00b\n") == [
        "Fichier illisible (encodage non reconnu) : enregistrez-le en « CSV UTF-8 »."
    ]
    assert errors_of(b"1;a\x07b\n") == ["Ligne 1 : le nom contient un caractère invalide."]


def test_blank_lines_count_in_line_numbers():
    assert errors_of(b"1;A\n\n\n;B\n") == ["Ligne 4 : numéro vide."]


def test_limits_are_inclusive():
    number, name = "1" * 20, "A" * 200
    assert parse_roster(f"{number};{name}\n".encode()).entries == [Entry(number, name)]
