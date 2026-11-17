"""Archive ZIP de l'import (IMP-08) : un seul `.txt`, chemins relatifs à son dossier, limites."""

import io
import zipfile

import pytest

from bank import archive
from bank.archive import ArchiveError, is_archive, read


def make_zip(files: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def refused(data: bytes) -> str:
    with pytest.raises(ArchiveError) as raised:
        read(data)
    return str(raised.value)


def test_signature():
    assert is_archive(make_zip({"a.txt": b""}))
    assert is_archive(make_zip({}))
    assert not is_archive(b"* Q ?\n+ Oui\n- Non\n")


def test_files_are_relative_to_the_txt_folder():
    found = read(
        make_zip(
            {
                "qcm/chimie.txt": b"* Q ?",
                "qcm/img/a.png": b"A",
                "commun/b.png": b"B",
                "qcm/": b"",  # dossier
            }
        )
    )
    assert (found.txt_name, found.txt) == ("qcm/chimie.txt", b"* Q ?")
    assert found.files == {"img/a.png": b"A", "../commun/b.png": b"B"}


def test_hidden_and_macos_files_are_ignored():
    found = read(
        make_zip(
            {
                "q.txt": b"Q",
                "__MACOSX/._q.txt": b"x",
                ".cache/notes.txt": b"x",
                "img/._a.png": b"x",
                ".DS_Store": b"x",
                "img/a.png": b"A",
            }
        )
    )
    assert found.txt == b"Q"
    assert found.files == {"img/a.png": b"A"}


def test_exactly_one_txt():
    assert refused(make_zip({"a.png": b"A"})) == (
        "L'archive ne contient aucun fichier AMC-TXT (.txt)."
    )
    assert refused(make_zip({"a.txt": b"", "b/c.TXT": b""})) == (
        "L'archive contient plusieurs fichiers AMC-TXT (.txt) : a.txt, b/c.TXT."
    )


def test_trapped_paths_are_only_keys():  # zip-slip : rien n'est écrit sur le disque
    found = read(make_zip({"q.txt": b"Q", "../../etc/x.png": b"X", "/abs/y.png": b"Y"}))
    assert found.files == {"../../etc/x.png": b"X", "abs/y.png": b"Y"}


def test_windows_separators():
    found = read(make_zip({"qcm\\q.txt": b"Q", "qcm\\img\\a.png": b"A"}))
    assert found.files == {"img/a.png": b"A"}


def test_archive_size_limit(monkeypatch):
    data = make_zip({"q.txt": b"Q"})
    monkeypatch.setattr(archive, "MAX_ARCHIVE_BYTES", len(data))
    assert read(data).txt == b"Q"
    monkeypatch.setattr(archive, "MAX_ARCHIVE_BYTES", len(data) - 1)
    assert refused(data) == "Archive trop volumineuse : 0 Mo au plus."


def test_unpacked_size_is_counted_while_reading(monkeypatch):
    # Bombe : quelques Ko compressés ; la lecture s'arrête au budget, sans tout décompresser.
    data = make_zip({"q.txt": b"Q", "a.png": b"0" * 100_000})
    assert len(data) < 2_000
    monkeypatch.setattr(archive, "MAX_UNPACKED_BYTES", 100_001)
    assert read(data).files["a.png"] == b"0" * 100_000
    monkeypatch.setattr(archive, "MAX_UNPACKED_BYTES", 100_000)
    assert refused(data).startswith("Archive trop volumineuse une fois décompressée")


def test_announced_size_is_not_trusted(monkeypatch):
    data = bytearray(make_zip({"q.txt": b"Q", "a.png": b"0" * 100_000}))
    # Taille décompressée annoncée ramenée à 1 octet dans l'en-tête local et le répertoire.
    for offset in _size_fields(bytes(data), b"a.png"):
        data[offset : offset + 4] = (1).to_bytes(4, "little")
    # Une taille fausse ne fait pas lire moins : la somme de contrôle ne correspond plus.
    assert refused(bytes(data)) == "Archive ZIP illisible."


def _size_fields(data: bytes, name: str | bytes):
    """Positions du champ « taille décompressée » des en-têtes qui nomment `name`."""
    name = name if isinstance(name, bytes) else name.encode()
    positions = []
    start = 0
    while (index := data.find(b"PK\x03\x04", start)) >= 0:
        if data[index + 30 : index + 30 + len(name)] == name:
            positions.append(index + 22)
        start = index + 4
    start = 0
    while (index := data.find(b"PK\x01\x02", start)) >= 0:
        if data[index + 46 : index + 46 + len(name)] == name:
            positions.append(index + 24)
        start = index + 4
    return positions


def test_entries_limit(monkeypatch):
    data = make_zip({"q.txt": b"Q", "a.png": b"A"})
    monkeypatch.setattr(archive, "MAX_ENTRIES", 2)
    assert read(data).files == {"a.png": b"A"}
    monkeypatch.setattr(archive, "MAX_ENTRIES", 1)
    assert refused(data) == "Archive de plus de 1 fichiers."


@pytest.mark.parametrize(
    "data",
    [
        b"PK\x03\x04 tronquee",
        make_zip({"q.txt": b"Quiz"}, zipfile.ZIP_STORED).replace(b"Quiz", b"Quix"),  # CRC faux
    ],
)
def test_unreadable(data):
    assert refused(data) == "Archive ZIP illisible."
