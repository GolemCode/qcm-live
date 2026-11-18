"""Images des énoncés et des propositions (CNT-03), importées avec un fichier AMC-TXT (IMP-08).

Module pur : contrôle du contenu (PNG, JPEG, SVG sans DOCTYPE ni entité) et nom stocké, tiré du
contenu : la même image importée deux fois ne fait qu'une.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath
from xml.etree import ElementTree

MAX_IMAGE_BYTES = 2_000_000
TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}
SIGNATURES = {"image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff"}
PDF_EPS = frozenset({"pdf", "eps"})
STEM_MAX_LENGTH = 40
SVG_FORBIDDEN_RE = re.compile(rb"<!(DOCTYPE|ENTITY)", re.IGNORECASE)


class ImageError(ValueError):
    """Image refusée ; le message nomme le fichier et la raison."""


@dataclass(frozen=True)
class CheckedImage:
    name: str  # nom stocké, cité par le texte : `graphe-3fa9c2d1.png`
    sha256: str
    content_type: str
    data: bytes


def _svg(data: bytes) -> bool:
    """XML dont la racine est `svg`, sans DOCTYPE ni entité (aucune expansion possible)."""
    if b"\x00" in data or SVG_FORBIDDEN_RE.search(data):  # UTF-16 cacherait un DOCTYPE
        return False
    try:
        root = ElementTree.fromstring(data)  # noqa: S314 (sans DOCTYPE : ni entité ni DTD)
    except ElementTree.ParseError:
        return False
    return root.tag in ("svg", "{http://www.w3.org/2000/svg}svg")


def _stem(path: str) -> str:
    stem = unicodedata.normalize("NFKD", PurePosixPath(path).stem)
    stem = "".join(c for c in stem if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")[:STEM_MAX_LENGTH] or "image"


def check(path: str, data: bytes) -> CheckedImage:
    """L'image prête à enregistrer ; `ImageError` si son format ou son contenu est refusé."""
    extension = PurePosixPath(path).suffix.lower().removeprefix(".")
    if extension in PDF_EPS:
        raise ImageError(f"image PDF ou EPS, à convertir en PNG, JPEG ou SVG : {path}")
    content_type = TYPES.get(extension)
    if content_type is None:
        raise ImageError(f"format d'image non pris en charge (PNG, JPEG ou SVG) : {path}")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError(f"image de plus de 2 Mo : {path}")
    signature = SIGNATURES.get(content_type)
    if not (data.startswith(signature) if signature else _svg(data)):
        raise ImageError(f"image illisible : {path}")
    digest = hashlib.sha256(data).hexdigest()
    name = f"{_stem(path)}-{digest[:8]}.{extension}"
    return CheckedImage(name, digest, content_type, data)
