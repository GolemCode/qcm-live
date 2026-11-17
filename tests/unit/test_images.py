"""Contrôle des images importées (CNT-03, IMP-08) : formats, taille, contenu, nom stocké."""

import pytest

from bank.images import MAX_IMAGE_BYTES, ImageError, check

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 8
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>'


@pytest.mark.parametrize(
    ("path", "data", "content_type"),
    [
        ("a.png", PNG, "image/png"),
        ("a.JPG", JPEG, "image/jpeg"),
        ("a.jpeg", JPEG, "image/jpeg"),
        ("a.svg", SVG, "image/svg+xml"),
        ("a.svg", b"<?xml version='1.0'?><svg/>", "image/svg+xml"),
    ],
)
def test_accepted_formats(path, data, content_type):
    image = check(path, data)
    assert image.content_type == content_type
    assert image.data == data


@pytest.mark.parametrize(
    ("path", "data", "message"),
    [
        ("f.pdf", b"%PDF", "image PDF ou EPS, à convertir en PNG, JPEG ou SVG : f.pdf"),
        ("f.EPS", b"%!PS", "image PDF ou EPS, à convertir en PNG, JPEG ou SVG : f.EPS"),
        ("g.gif", b"GIF89a", "format d'image non pris en charge (PNG, JPEG ou SVG) : g.gif"),
        ("sans", PNG, "format d'image non pris en charge (PNG, JPEG ou SVG) : sans"),
        ("a.png", JPEG, "image illisible : a.png"),
        ("a.jpg", PNG, "image illisible : a.jpg"),
        ("a.svg", b"<html/>", "image illisible : a.svg"),
        ("a.svg", b"<svg", "image illisible : a.svg"),
        # Ni DTD ni entité : aucune expansion possible (« milliard de rires »).
        ("a.svg", b'<!DOCTYPE svg [<!ENTITY a "x">]><svg>&a;</svg>', "image illisible : a.svg"),
        ("a.svg", b'<!doctype svg SYSTEM "file:///etc/passwd"><svg/>', "image illisible : a.svg"),
        ("a.svg", "<!DOCTYPE x><svg/>".encode("utf-16"), "image illisible : a.svg"),
    ],
)
def test_refused(path, data, message):
    with pytest.raises(ImageError) as raised:
        check(path, data)
    assert str(raised.value) == message


def test_size_limit():
    assert check("a.png", PNG + b"0" * (MAX_IMAGE_BYTES - len(PNG)))
    with pytest.raises(ImageError, match=r"image de plus de 2 Mo : a\.png"):
        check("a.png", PNG + b"0" * (MAX_IMAGE_BYTES - len(PNG) + 1))


def test_stored_name_comes_from_the_content():
    image = check("img/Graphe été (2).png", PNG)
    assert image.name == f"Graphe_ete_2-{image.sha256[:8]}.png"
    assert check("autre/Graphe été (2).png", PNG).name == image.name
    assert check("Graphe été (2).png", PNG + b"1").name != image.name


@pytest.mark.parametrize(
    ("path", "stem"), [("€.png", "image"), (f"{'x' * 60}.png", "x" * 40), ("--.png", "image")]
)
def test_stored_name_is_short_and_plain(path, stem):
    assert check(path, PNG).name.rsplit("-", 1)[0] == stem
