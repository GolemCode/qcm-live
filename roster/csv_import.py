"""Lecture de la liste d'un groupe au format CSV (numéro, nom) — SPEC.md §2 bis.

Fonction pure : des octets en entrée, la liste des étudiants ou toutes les erreurs en sortie.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass

MAX_BYTES = 1_000_000  # largement assez pour une promotion entière
MAX_NUMBER_LENGTH = 20
MAX_NAME_LENGTH = 200
MAX_REPORTED_ERRORS = 20
# Chiffres ASCII seulement : « \d » accepterait aussi les chiffres pleine chasse ou arabes,
# que l'étudiant ne pourrait pas taper sur le pavé numérique de son téléphone.
NUMBER_RE = re.compile(rf"[0-9]{{1,{MAX_NUMBER_LENGTH}}}")
ENCODING_ERROR = "Fichier illisible (encodage non reconnu) : enregistrez-le en « CSV UTF-8 »."


@dataclass(frozen=True)
class Entry:
    number: str
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


def _is_header(cells: list[str]) -> bool:
    return len(cells) == 2 and all(cells) and not any(ch.isdigit() for ch in cells[0])


def _has_control_char(text: str) -> bool:
    return any(unicodedata.category(ch) == "Cc" for ch in text)


def _line_errors(line: int, cells: list[str], seen: dict[str, int]) -> list[str]:
    if len(cells) != 2:
        return [f"Ligne {line} : format incorrect, 2 colonnes attendues (numéro, nom)."]
    number, name = cells
    errors = []
    if not number:
        errors.append(f"Ligne {line} : numéro vide.")
    elif not NUMBER_RE.fullmatch(number):
        errors.append(
            f"Ligne {line} : le numéro « {number} » ne doit contenir que des chiffres"
            f" ({MAX_NUMBER_LENGTH} au plus)."
        )
    elif number in seen:
        errors.append(f"Ligne {line} : numéro {number} en double (déjà ligne {seen[number]}).")
    if not name:
        errors.append(f"Ligne {line} : nom vide.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Ligne {line} : nom trop long ({MAX_NAME_LENGTH} caractères au plus).")
    elif _has_control_char(name):
        errors.append(f"Ligne {line} : le nom contient un caractère invalide.")
    return errors


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
    seen: dict[str, int] = {}
    header = None
    first_row = True
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
        while len(cells) > 2 and not cells[-1]:
            cells.pop()  # colonnes vides en fin de ligne (exports d'Excel)
        if first_row:
            first_row = False
            if _is_header(cells):
                header = (line, " ; ".join(cells))
                continue
        line_errors = _line_errors(line, cells, seen)
        if line_errors:
            room = MAX_REPORTED_ERRORS - len(errors)
            errors += line_errors[:room]
            hidden += len(line_errors[room:])
            continue
        seen[cells[0]] = line
        entries.append(Entry(*cells))

    if hidden:
        errors.append(f"… et {hidden} autres erreurs.")
    if errors:
        raise RosterError(errors)
    if not entries:
        raise RosterError(["Le fichier ne contient aucun étudiant."])
    return Roster(entries, header)
