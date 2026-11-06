"""Lecture de la liste d'un groupe au format CSV (numéro, nom) — SPEC.md §2 bis.

Fonction pure : des octets en entrée, la liste des étudiants ou toutes les erreurs en sortie.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass

MAX_BYTES = 1_000_000  # largement assez pour une promotion entière
MAX_NAME_LENGTH = 200
MAX_REPORTED_ERRORS = 20
NUMBER_RE = re.compile(r"\d{1,20}")


@dataclass(frozen=True)
class Entry:
    number: str
    name: str


class RosterError(ValueError):
    """Fichier refusé ; `messages` désigne chaque ligne fautive."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("\n".join(messages))
        self.messages = messages


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp1252")  # anciens exports d'Excel sous Windows
    except UnicodeDecodeError:
        raise RosterError(
            ["Fichier illisible (encodage inconnu) : enregistrez-le en « CSV UTF-8 »."]
        ) from None


def _is_header(cells: list[str]) -> bool:
    return len(cells) == 2 and all(cells) and not any(ch.isdigit() for ch in cells[0])


def _line_errors(line: int, cells: list[str], seen: dict[str, int]) -> list[str]:
    if len(cells) != 2:
        return [f"Ligne {line} : format incorrect, 2 colonnes attendues (numéro, nom)."]
    number, name = cells
    errors = []
    if not number:
        errors.append(f"Ligne {line} : numéro vide.")
    elif not NUMBER_RE.fullmatch(number):
        errors.append(
            f"Ligne {line} : le numéro « {number} » ne doit contenir que des chiffres (20 au plus)."
        )
    elif number in seen:
        errors.append(f"Ligne {line} : numéro {number} en double (déjà ligne {seen[number]}).")
    if not name:
        errors.append(f"Ligne {line} : nom vide.")
    elif len(name) > MAX_NAME_LENGTH:
        errors.append(f"Ligne {line} : nom trop long ({MAX_NAME_LENGTH} caractères au plus).")
    return errors


def parse_roster(data: bytes) -> list[Entry]:
    """Étudiants du fichier, dans l'ordre ; lève RosterError si une seule ligne est fautive."""
    if len(data) > MAX_BYTES:
        raise RosterError([f"Fichier trop volumineux ({MAX_BYTES // 1000} ko au plus)."])
    lines = _decode(data).splitlines()
    first = next((line for line in lines if line.strip()), "")
    reader = csv.reader(lines, delimiter=";" if ";" in first else ",")

    entries: list[Entry] = []
    errors: list[str] = []
    seen: dict[str, int] = {}
    first_row = True
    for row in reader:
        cells = [cell.strip() for cell in row]
        if not any(cells):
            continue  # ligne vide
        while len(cells) > 2 and not cells[-1]:
            cells.pop()  # colonnes vides en fin de ligne (exports d'Excel)
        if first_row and _is_header(cells):
            first_row = False
            continue
        first_row = False
        line_errors = _line_errors(reader.line_num, cells, seen)
        if line_errors:
            errors += line_errors
            continue
        seen[cells[0]] = reader.line_num
        entries.append(Entry(*cells))

    if len(errors) > MAX_REPORTED_ERRORS:
        hidden = len(errors) - MAX_REPORTED_ERRORS
        errors = [*errors[:MAX_REPORTED_ERRORS], f"… et {hidden} autres erreurs."]
    if errors:
        raise RosterError(errors)
    if not entries:
        raise RosterError(["Le fichier ne contient aucun étudiant."])
    return entries
