"""Archive ZIP envoyée à l'import (IMP-08) : un fichier AMC-TXT et ses images.

Module pur. L'archive est lue en mémoire, jamais extraite sur le disque : un chemin piégé
(`../../x`, `/etc/x`) n'est qu'une clé qu'aucun texte ne désigne. La taille réelle de chaque
fichier est comptée pendant la lecture, sans se fier à celle que l'archive annonce.
"""

from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass

MAX_ARCHIVE_BYTES = 20_000_000
MAX_UNPACKED_BYTES = 50_000_000
MAX_ENTRIES = 500
SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06")  # archive non vide, archive vide
CHUNK = 64 * 1024


class ArchiveError(ValueError):
    """Archive refusée ; le message dit pourquoi."""


@dataclass(frozen=True)
class Archive:
    txt_name: str  # chemin du fichier AMC-TXT dans l'archive
    txt: bytes
    files: dict[str, bytes]  # les autres fichiers, par chemin relatif au dossier du `.txt`


def is_archive(data: bytes) -> bool:
    return data.startswith(SIGNATURES)


def _path(name: str) -> str:
    """Chemin normalisé : séparateurs de Windows, et sans `/` au début."""
    return posixpath.normpath(name.replace("\\", "/").lstrip("/"))


def _ignored(path: str) -> bool:
    """Fichiers cachés et métadonnées ajoutées par macOS (`__MACOSX/`, `._x`, `.DS_Store`)."""
    parts = path.split("/")
    return parts[0] == "__MACOSX" or any(part.startswith(".") and part != ".." for part in parts)


def _read(archive: zipfile.ZipFile, info: zipfile.ZipInfo, budget: int) -> bytes:
    """Le contenu, lu par morceaux ; `ArchiveError` s'il dépasse le budget restant."""
    data = bytearray()
    with archive.open(info) as stream:
        while chunk := stream.read(CHUNK):
            data += chunk
            if len(data) > budget:
                raise ArchiveError(
                    f"Archive trop volumineuse une fois décompressée : "
                    f"{MAX_UNPACKED_BYTES // 1_000_000} Mo au plus."
                )
    return bytes(data)


def read(data: bytes) -> Archive:
    """Le fichier AMC-TXT de l'archive et les autres fichiers ; `ArchiveError` si refusée."""
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ArchiveError(
            f"Archive trop volumineuse : {MAX_ARCHIVE_BYTES // 1_000_000} Mo au plus."
        )
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ArchiveError(f"Archive de plus de {MAX_ENTRIES} fichiers.")
            entries = [
                (_path(info.filename), info)
                for info in infos
                if not info.is_dir() and not _ignored(_path(info.filename))
            ]
            txts = sorted(path for path, _ in entries if path.lower().endswith(".txt"))
            if not txts:
                raise ArchiveError("L'archive ne contient aucun fichier AMC-TXT (.txt).")
            if len(txts) > 1:
                raise ArchiveError(
                    f"L'archive contient plusieurs fichiers AMC-TXT (.txt) : {', '.join(txts)}."
                )
            folder = posixpath.dirname(txts[0]) or "."
            budget = MAX_UNPACKED_BYTES
            txt, files = b"", {}
            for path, info in entries:
                content = _read(archive, info, budget)
                budget -= len(content)
                if path == txts[0]:
                    txt = content
                else:
                    files[posixpath.relpath(path, folder)] = content
    except (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError, RuntimeError, EOFError):
        # CRC faux, compression inconnue, archive chiffrée ou tronquée
        raise ArchiveError("Archive ZIP illisible.") from None
    return Archive(txts[0], txt, files)
