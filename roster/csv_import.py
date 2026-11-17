"""Lecture de la liste d'un groupe au format CSV — SPEC.md §2 bis.

Deux formats : celui d'I14, à en-tête `n°;numéro étudiant;nom` (GRP-05), et l'ancien
(numéro, nom ; en-tête facultatif), où le n° est le rang de l'étudiant dans le fichier.

Fonction pure : des octets en entrée, la liste des étudiants ou toutes les erreurs en sortie.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass

MAX_BYTES = 1_000_000  # largement assez pour une promotion entière
MAX_STUDENTS = 70  # GRP-05
MAX_LIST_NUMBER = 999
MAX_STUDENT_NUMBER_LENGTH = 20
MAX_NAME_LENGTH = 200
MAX_REPORTED_ERRORS = 20
# Chiffres ASCII seulement : « \d » accepterait aussi les chiffres pleine chasse ou arabes.
LIST_NUMBER_RE = re.compile(r"[0-9]{1,3}")  # « 0001 » refusé : 3 chiffres au plus
HEADER = ("n°", "numéro étudiant", "nom")
ENCODING_ERROR = "Fichier illisible (encodage non reconnu) : enregistrez-le en « CSV UTF-8 »."


@dataclass(frozen=True)
class Entry:
    list_number: int
    student_number: str  # vide s'il manque
    name: str


@dataclass(frozen=True)
class Roster:
    entries: list[Entry]
    header: tuple[int, str] | None = None  # (ligne, texte) ignorée comme en-tête : à signaler


class RosterError(ValueError):
    """Fichier refusé ; `messages` désigne chaque ligne fautive."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("\n".join(messages))
        self.messages = messages


def _decode(data: bytes) -> str:
    if b"\x00" in data:  # UTF-16 (« Texte Unicode » d'Excel) ou fichier binaire
        raise RosterError([ENCODING_ERROR])
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp1252")  # anciens exports d'Excel sous Windows
    except UnicodeDecodeError:
        raise RosterError([ENCODING_ERROR]) from None


def _header_key(cell: str) -> str:
    """Cellule d'en-tête sans accents, espaces ni majuscules ; « nº » s'écrit « no »."""
    letters = unicodedata.normalize("NFKD", cell)
    return "".join(
        ch for ch in letters if not unicodedata.combining(ch) and not ch.isspace()
    ).lower()


HEADER_KEYS = [{_header_key(title)} for title in HEADER]
HEADER_KEYS[0].add("no")  # « No », « nº »


def _trim(cells: list[str], width: int) -> list[str]:
    """Sans les colonnes vides en fin de ligne (exports d'Excel), jusqu'à `width` colonnes."""
    while len(cells) > width and not cells[-1]:
        cells = cells[:-1]
    return cells


def _is_new_header(cells: list[str]) -> bool:
    cells = _trim(cells, len(HEADER))
    return len(cells) == len(HEADER) and all(
        _header_key(cell) in keys for cell, keys in zip(cells, HEADER_KEYS, strict=True)
    )


def _is_old_header(cells: list[str]) -> bool:
    return len(cells) == 2 and all(cells) and not any(ch.isdigit() for ch in cells[0])


def _has_control_char(text: str) -> bool:
    return any(unicodedata.category(ch) == "Cc" for ch in text)


class _Checker:
    """Contrôles ligne par ligne ; retient chaque n° et numéro étudiant valide, même sur une
    ligne fautive par ailleurs : un doublon plus loin est signalé dans le même rapport."""

    def __init__(self, new_format: bool) -> None:
        self.new_format = new_format
        self.width = 3 if new_format else 2
        self.list_numbers: dict[int, int] = {}
        self.student_numbers: dict[str, int] = {}
        self.rank = 0  # ancien format : rang de l'étudiant dans le fichier

    def entry(self, line: int, cells: list[str]) -> tuple[Entry | None, list[str]]:
        self.rank += 1
        cells = _trim(cells, self.width)
        if len(cells) != self.width:
            return None, [self._format_error(line, len(cells))]
        if self.new_format:
            list_cell, student_number, name = cells
            list_number, errors = self._list_number(line, list_cell)
        else:
            (student_number, name), list_number, errors = cells, self.rank, []
        number_errors = self._student_number(line, student_number)
        if list_number is not None:
            self.list_numbers[list_number] = line
        if student_number and not number_errors:
            self.student_numbers[student_number] = line
        errors += number_errors + self._name(line, name)
        if errors or list_number is None:
            return None, errors
        return Entry(list_number, student_number, name), []

    def _format_error(self, line: int, width: int) -> str:
        if self.new_format:
            return (
                f"Ligne {line} : format incorrect, 3 colonnes attendues (n°, numéro étudiant, nom)."
            )
        message = f"Ligne {line} : format incorrect, 2 colonnes attendues (numéro, nom)"
        if width == 3:
            header = ";".join(HEADER)
            return (
                f"{message} ; pour 3 colonnes, l'en-tête « {header} » est attendu"
                " en première ligne."
            )
        return f"{message}."

    def _list_number(self, line: int, cell: str) -> tuple[int | None, list[str]]:
        if not cell:
            return None, [f"Ligne {line} : n° vide."]
        if not LIST_NUMBER_RE.fullmatch(cell) or not 1 <= int(cell) <= MAX_LIST_NUMBER:
            return None, [
                f"Ligne {line} : le n° « {cell} » doit être un entier de 1 à {MAX_LIST_NUMBER}."
            ]
        number = int(cell)
        if number in self.list_numbers:
            first = self.list_numbers[number]
            return None, [f"Ligne {line} : n° {number} en double (déjà ligne {first})."]
        return number, []

    def _student_number(self, line: int, number: str) -> list[str]:
        if len(number) > MAX_STUDENT_NUMBER_LENGTH:
            limit = MAX_STUDENT_NUMBER_LENGTH
            return [f"Ligne {line} : numéro étudiant trop long ({limit} caractères au plus)."]
        if _has_control_char(number):
            return [f"Ligne {line} : le numéro étudiant contient un caractère invalide."]
        if number in self.student_numbers:
            first = self.student_numbers[number]
            return [f"Ligne {line} : numéro étudiant « {number} » en double (déjà ligne {first})."]
        return []

    def _name(self, line: int, name: str) -> list[str]:
        if not name:
            return [f"Ligne {line} : nom vide."]
        if len(name) > MAX_NAME_LENGTH:
            return [f"Ligne {line} : nom trop long ({MAX_NAME_LENGTH} caractères au plus)."]
        if _has_control_char(name):
            return [f"Ligne {line} : le nom contient un caractère invalide."]
        return []


def _delimiter(text: str) -> str:
    first = next((line for line in re.split(r"\r\n|\r|\n", text) if line.strip()), "")
    return ";" if ";" in first else ","


def parse_roster(data: bytes) -> Roster:
    """Étudiants du fichier, dans l'ordre ; lève RosterError si une seule ligne est fautive.

    Il suffit de lire MAX_BYTES + 1 octets du fichier pour savoir s'il est trop gros.
    Les numéros de ligne sont ceux du fichier : seuls \\r\\n, \\n et \\r terminent une ligne.
    """
    if len(data) > MAX_BYTES:
        raise RosterError([f"Fichier trop volumineux ({MAX_BYTES // 1000} ko au plus)."])
    text = _decode(data)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=_delimiter(text))

    entries: list[Entry] = []
    errors: list[str] = []  # les MAX_REPORTED_ERRORS premières seulement…
    hidden = 0  # … les suivantes sont comptées
    header = None
    checker = None  # choisi sur la première ligne non vide
    while True:
        line = reader.line_num + 1  # première ligne de l'enregistrement (guillemets multilignes)
        try:
            row = next(reader, None)
        except csv.Error:
            raise RosterError([f"Ligne {line} : format incorrect (champ illisible)."]) from None
        if row is None:
            break
        cells = [cell.strip() for cell in row]
        if not any(cells):
            continue  # ligne vide
        if checker is None:
            checker = _Checker(new_format=_is_new_header(cells))
            if checker.new_format:
                continue
            cells = _trim(cells, checker.width)
            if _is_old_header(cells):
                header = (line, " ; ".join(cells))
                continue
        entry, line_errors = checker.entry(line, cells)
        if entry:
            entries.append(entry)
        room = MAX_REPORTED_ERRORS - len(errors)
        errors += line_errors[:room]
        hidden += len(line_errors[room:])

    if hidden:
        errors.append(f"… et {hidden} autres erreurs.")
    if errors:
        raise RosterError(errors)
    if not entries:
        raise RosterError(["Le fichier ne contient aucun étudiant."])
    if len(entries) > MAX_STUDENTS:
        raise RosterError(
            [f"Le fichier contient {len(entries)} étudiants : {MAX_STUDENTS} au plus."]
        )
    return Roster(entries, header)
