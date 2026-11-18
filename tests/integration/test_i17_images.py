"""I17 : images importées (CNT-03, IMP-08) : leur adresse publique, leurs en-têtes, et l'import
d'une archive (création, partage d'une même image, empreinte du réimport)."""

import io
import zipfile

import pytest

from bank.importer import import_quiz, preview, sha256
from bank.models import Image

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
TXT = b"* Voir !img/a.png! ?\n+ !b.svg!\n- Non\n"


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def test_image_is_served_without_running_anything(client):
    image = Image.objects.create(
        name="b-12345678.svg", sha256="0" * 64, content_type="image/svg+xml", data=SVG
    )
    response = client.get(f"/images/{image.name}")  # sans compte : le téléphone la charge
    assert response.status_code == 200
    assert response.content == SVG
    assert response["Content-Type"] == "image/svg+xml"
    assert response["Content-Security-Policy"] == (
        "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    )
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "immutable" in response["Cache-Control"]


def test_unknown_image(client):
    assert client.get("/images/inconnue.png").status_code == 404


def test_archive_import_creates_each_image_once():
    data = make_zip({"qcm/q.txt": TXT, "qcm/img/a.png": PNG, "qcm/b.svg": SVG})
    quiz = import_quiz(data, "q.zip")
    assert sorted(Image.objects.values_list("content_type", flat=True)) == [
        "image/png",
        "image/svg+xml",
    ]
    question = quiz.ordered_questions().get()
    png = Image.objects.get(content_type="image/png")
    assert question.text == f"Voir \\includegraphics{{{png.name}}} ?"
    assert bytes(png.data) == PNG
    # Un autre fichier qui cite la même image la partage.
    import_quiz(make_zip({"r.txt": b"* Encore !a.png! ?\n+ Oui\n- Non\n", "a.png": PNG}), "r.zip")
    assert Image.objects.count() == 2


def test_fingerprint_follows_the_images():
    plain = b"* Q ?\n+ Oui\n- Non\n"
    assert preview(make_zip({"q.txt": plain}), "q.zip").sha256 == sha256(plain)
    first = preview(make_zip({"q.txt": TXT, "img/a.png": PNG, "b.svg": SVG}), "q.zip")
    other = preview(make_zip({"q.txt": TXT, "img/a.png": PNG + b"1", "b.svg": SVG}), "q.zip")
    assert len({first.sha256, other.sha256, sha256(TXT)}) == 3
    # Une archive refaite à l'identique (autre ordre, autre date) garde son empreinte.
    again = preview(make_zip({"b.svg": SVG, "img/a.png": PNG, "q.txt": TXT}), "q.zip")
    assert again.sha256 == first.sha256


def test_same_name_other_content_is_refused():
    data = make_zip({"q.txt": b"* Voir !a.png! ?\n+ Oui\n- Non\n", "a.png": PNG})
    found = preview(data, "q.zip")
    (image,) = found.parsed.images
    Image.objects.create(name=image.name, sha256="f" * 64, content_type="image/png", data=PNG)
    with pytest.raises(ValueError, match="une autre image porte déjà ce nom"):
        import_quiz(data, "q.zip")
