"""Lecture du CSV d'un groupe (SPEC.md §2 bis) : tous les cas, sur une fonction pure.

Deux formats : celui d'I14 (en-tête `n°;numéro étudiant;nom`, GRP-05) et l'ancien (numéro, nom ;
le n° est alors le rang dans le fichier).
"""

import pytest

from roster.csv_import import MAX_BYTES, MAX_STUDENTS, Entry, RosterError, parse_roster

HEADER = "n°;numéro étudiant;nom\n"


def errors_of(data: bytes) -> list[str]:
    with pytest.raises(RosterError) as excinfo:
        parse_roster(data)
    return excinfo.value.messages


def new(*lines: str, header: str = HEADER) -> bytes:
    """Fichier au format d'I14 : l'en-tête, puis les lignes données."""
    return (header + "".join(f"{line}\n" for line in lines)).encode()


# --- Nouveau format (I14, GRP-05) -------------------------------------------------------------


def test_new_format_keeps_numbers_gaps_and_order_of_the_file():
    data = new("12;21904567;DUPONT Jeanne", "3;;MARTIN Paul", "7;INE-0042b;Ng Anh")
    roster = parse_roster(data)
    assert roster.entries == [
        Entry(12, "21904567", "DUPONT Jeanne"),
        Entry(3, "", "MARTIN Paul"),  # numéro étudiant facultatif
        Entry(7, "INE-0042b", "Ng Anh"),  # texte libre
    ]
    assert roster.header is None  # l'en-tête attendu n'est pas signalé comme ignoré


@pytest.mark.parametrize(
    "header",
    [
        "n°;numéro étudiant;nom",
        "N°;Numéro Étudiant;NOM",
        " n° ; numero  etudiant ; nom ",
        "no;numero etudiant;nom",
        "nº;numéro étudiant;nom",  # indicateur ordinal masculin
        "N°,Numéro étudiant,Nom",
        "n°;numéro étudiant;nom;;",
    ],
)
def test_new_format_header_variants(header):
    sep = "," if "," in header else ";"
    data = f"{header}\n1{sep}00123{sep}DURAND Élise\n".encode()
    assert parse_roster(data).entries == [Entry(1, "00123", "DURAND Élise")]


def test_new_format_header_after_blank_lines_with_comma_and_quotes():
    data = b'\n\nn\xc2\xb0,num\xc3\xa9ro \xc3\xa9tudiant,nom\n2,,"DUPONT, Jeanne"\n'
    assert parse_roster(data).entries == [Entry(2, "", "DUPONT, Jeanne")]


def test_new_format_in_windows_1252():
    data = "N°;Numéro étudiant;Nom\r\n1;00123;DURAND Élise\r\n".encode("cp1252")
    assert parse_roster(data).entries == [Entry(1, "00123", "DURAND Élise")]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (";1;A", "Ligne 2 : n° vide."),
        ("0;1;A", "Ligne 2 : le n° « 0 » doit être un entier de 1 à 999."),
        ("1000;1;A", "Ligne 2 : le n° « 1000 » doit être un entier de 1 à 999."),
        ("0001;1;A", "Ligne 2 : le n° « 0001 » doit être un entier de 1 à 999."),
        ("-1;1;A", "Ligne 2 : le n° « -1 » doit être un entier de 1 à 999."),
        ("1.5;1;A", "Ligne 2 : le n° « 1.5 » doit être un entier de 1 à 999."),
        ("a;1;A", "Ligne 2 : le n° « a » doit être un entier de 1 à 999."),
        ("\uff11;1;A", "Ligne 2 : le n° « \uff11 » doit être un entier de 1 à 999."),
        ("1;" + "x" * 21 + ";A", "Ligne 2 : numéro étudiant trop long (20 caractères au plus)."),
        ("1;a\x07b;A", "Ligne 2 : le numéro étudiant contient un caractère invalide."),
        ("1;1;", "Ligne 2 : nom vide."),
        ("1;1;" + "A" * 201, "Ligne 2 : nom trop long (200 caractères au plus)."),
        ("1;1;a\x07b", "Ligne 2 : le nom contient un caractère invalide."),
        ("1;A", "Ligne 2 : format incorrect, 3 colonnes attendues (n°, numéro étudiant, nom)."),
        ("1;2;A;B", "Ligne 2 : format incorrect, 3 colonnes attendues (n°, numéro étudiant, nom)."),
    ],
)
def test_new_format_line_errors(line, expected):
    assert errors_of(new(line)) == [expected]


def test_new_format_duplicates():
    assert errors_of(new("12;A1;A", "5;B2;B", "12;C3;C")) == [
        "Ligne 4 : n° 12 en double (déjà ligne 2)."
    ]
    assert errors_of(new("1;A1;A", "2;A1;B")) == [
        "Ligne 3 : numéro étudiant « A1 » en double (déjà ligne 2)."
    ]
    # Vide : pas de doublon. Deux noms identiques : distingués par leur n°.
    assert parse_roster(new("1;;MARTIN Paul", "2;;MARTIN Paul")).entries == [
        Entry(1, "", "MARTIN Paul"),
        Entry(2, "", "MARTIN Paul"),
    ]


def test_new_format_reports_every_error_of_a_line():
    assert errors_of(new(";" + "x" * 21 + ";")) == [
        "Ligne 2 : n° vide.",
        "Ligne 2 : numéro étudiant trop long (20 caractères au plus).",
        "Ligne 2 : nom vide.",
    ]


def test_new_format_limits_just_accepted():
    data = new(f"1;{'x' * 20};{'A' * 200}", "999;;B")
    assert parse_roster(data).entries == [Entry(1, "x" * 20, "A" * 200), Entry(999, "", "B")]


def test_header_only_is_no_student():
    assert errors_of(new()) == ["Le fichier ne contient aucun étudiant."]


# --- 70 étudiants au plus (GRP-05) ------------------------------------------------------------


def test_seventy_students_are_accepted_seventy_one_refused():
    assert MAX_STUDENTS == 70
    lines = [f"{n};;ÉTUDIANT {n}" for n in range(1, 72)]
    assert len(parse_roster(new(*lines[:70])).entries) == 70
    assert errors_of(new(*lines)) == ["Le fichier contient 71 étudiants : 70 au plus."]
    old = "".join(f"{n};ÉTUDIANT {n}\n" for n in range(1, 72)).encode()
    assert errors_of(old) == ["Le fichier contient 71 étudiants : 70 au plus."]


# --- Ancien format (I2) : le n° est le rang dans le fichier -----------------------------------


def test_semicolon_with_header_and_blank_lines():
    data = b"numero;nom\n\n00123;DURAND Elise\n42;MARTIN Leo\n"
    assert parse_roster(data).entries == [
        Entry(1, "00123", "DURAND Elise"),
        Entry(2, "42", "MARTIN Leo"),
    ]


def test_comma_with_quotes_and_no_header():
    data = b'1,"DUPONT, Jeanne"\n2,ROUX Paul\n'
    assert parse_roster(data).entries == [
        Entry(1, "1", "DUPONT, Jeanne"),
        Entry(2, "2", "ROUX Paul"),
    ]


def test_rank_follows_the_file_not_the_numbers():
    data = b"55;C\n7;A\n0999;B\n"
    assert [(e.list_number, e.student_number) for e in parse_roster(data).entries] == [
        (1, "55"),
        (2, "7"),
        (3, "0999"),
    ]


def test_old_format_student_number_may_be_empty_or_hold_letters():
    """I14 : le numéro n'a plus à ne contenir que des chiffres ni à être rempli."""
    data = "1;A\n;B\n12a;C\n\uff11\uff12;D\n".encode()
    assert parse_roster(data).entries == [
        Entry(1, "1", "A"),
        Entry(2, "", "B"),
        Entry(3, "12a", "C"),
        Entry(4, "\uff11\uff12", "D"),
    ]


def test_semicolon_wins_when_present_in_first_line():
    assert parse_roster(b"1;Dupont, Jean\n").entries == [Entry(1, "1", "Dupont, Jean")]


@pytest.mark.parametrize(
    "data",
    [
        "1;Élise\n".encode(),
        "\ufeff1;Élise\n".encode(),
        "1;Élise\r\n".encode("cp1252"),
    ],
)
def test_encodings(data):
    assert parse_roster(data).entries == [Entry(1, "1", "Élise")]


def test_spaces_and_trailing_empty_columns_are_ignored():
    assert parse_roster(b" 7 ; Ng Anh ;;\n;;\n").entries == [Entry(1, "7", "Ng Anh")]


def test_header_requires_two_filled_cells_without_digit_in_first():
    # « ;B » n'est pas un en-tête : c'est un étudiant sans numéro.
    assert parse_roster(b";B\n1;A\n").entries == [Entry(1, "", "B"), Entry(2, "1", "A")]
    # « 12a;B » contient un chiffre : un étudiant, pas un en-tête.
    assert parse_roster(b"12a;B\n1;A\n").header is None
    # Seule la première ligne non vide peut être un en-tête.
    assert parse_roster(b"numero;nom\n1;A\nnumero;nom\n").entries[1] == Entry(2, "numero", "nom")


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"1;A\n2\n", "Ligne 2 : format incorrect, 2 colonnes attendues (numéro, nom)."),
        (b"1;A\n2;B;C;D\n", "Ligne 2 : format incorrect, 2 colonnes attendues (numéro, nom)."),
        (
            b"1;A;B\n",
            "Ligne 1 : format incorrect, 2 colonnes attendues (numéro, nom) ; pour 3 colonnes,"
            " l'en-tête « n°;numéro étudiant;nom » est attendu en première ligne.",
        ),
        (b"1;A\n2;B\n1;C\n", "Ligne 3 : numéro étudiant « 1 » en double (déjà ligne 1)."),
        (b"1;A\n2;\n", "Ligne 2 : nom vide."),
        (
            b"1;A\n" + b"1" * 21 + b";B\n",
            "Ligne 2 : numéro étudiant trop long (20 caractères au plus).",
        ),
        (b"1;" + b"A" * 201 + b"\n", "Ligne 1 : nom trop long (200 caractères au plus)."),
    ],
)
def test_line_errors(data, expected):
    assert errors_of(data)[0] == expected


def test_all_faulty_lines_are_reported_in_order():
    assert [m.split(" :")[0] for m in errors_of(b"1;A\n2\n3;C;D\n4;\n")] == [
        "Ligne 2",
        "Ligne 3",
        "Ligne 4",
    ]


def test_error_list_is_capped():
    # « 1x » contient un chiffre : la première ligne n'est pas prise pour un en-tête.
    messages = errors_of(b"".join(b"1x;\n" for _ in range(30)))
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


def test_control_characters_are_refused():
    assert errors_of(b"1;a\x00b\n") == [
        "Fichier illisible (encodage non reconnu) : enregistrez-le en « CSV UTF-8 »."
    ]
    assert errors_of(b"1;a\x07b\n") == ["Ligne 1 : le nom contient un caractère invalide."]
    assert errors_of(b"1\x07;a\n") == [
        "Ligne 1 : le numéro étudiant contient un caractère invalide."
    ]


def test_blank_lines_count_in_line_numbers():
    assert errors_of(b"1;A\n\n\n4;\n") == ["Ligne 4 : nom vide."]


def test_limits_are_inclusive():
    number, name = "1" * 20, "A" * 200
    assert parse_roster(f"{number};{name}\n".encode()).entries == [Entry(1, number, name)]
