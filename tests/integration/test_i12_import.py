"""Import AMC-TXT côté serveur (IMP-01, IMP-07) : `bank.importer` et ses deux vues."""

from decimal import Decimal as D

import pytest
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from bank import importer
from bank.amc_txt import MAX_BYTES, AmcSyntaxError
from bank.importer import NOTHING_TO_IMPORT, AlreadyImported, import_quiz, preview
from bank.models import PendingImport, Question, Quiz, QuizItem
from bank.views import EXPIRED
from tests.factories import make_question

pytestmark = pytest.mark.django_db

FILE = """Title: Contrôle
* Capitale de l'Italie ?
+ Rome
- Milan

*[group=calcul]{b=2} Combien font 2 + 2 ?
- 3
+{3} 4
- 5

** Nombres pairs ?
+ 2
- 3
""".encode()


def messages_of(response) -> list[str]:
    """Messages de la redirection ; la suivre les affiche, donc les retire du stockage."""
    found = [str(m) for m in get_messages(response.wsgi_request)]
    response.client.get(response["Location"])
    return found


# --- bank.importer ------------------------------------------------------------------------


def test_import_creates_the_quiz_in_file_order():
    quiz = import_quiz(FILE, "controle.txt")
    assert (quiz.title, quiz.source_name) == ("Contrôle", "controle.txt")
    assert quiz.source_sha256 == importer.sha256(FILE)
    items = list(QuizItem.objects.filter(quiz=quiz).order_by("position").select_related("question"))
    assert [i.position for i in items] == [1, 2, 3]
    first, second, third = (i.question for i in items)
    assert first.text == "Capitale de l'Italie ?" and first.amc_group == ""
    assert (second.scoring, second.amc_group) == ("b=2", "calcul")
    assert [c.points for c in second.choices.all()] == [None, D(3), None]
    assert third.kind == Question.Kind.MULTIPLE
    assert (third.scoring, third.none_of_these) == ("haut=2", True)


def test_identical_question_of_the_bank_is_shared():
    existing = make_question("Capitale de l'Italie ?", [("Rome", True), ("Milan", False)])
    same_text_other_answer = make_question(
        "Nombres pairs ?", [("2", False), ("3", True)], multiple=True, scoring="haut=2"
    )
    found = preview(FILE, "controle.txt")
    assert [shared for _, shared in found.rows()] == [True, False, False]
    assert found.existing == 1
    quiz = import_quiz(FILE, "controle.txt")
    assert existing in quiz.questions.all()
    assert same_text_other_answer not in quiz.questions.all()
    assert Question.objects.count() == 4


def test_the_oldest_identical_question_is_chosen():
    older = make_question("Capitale de l'Italie ?", [("Rome", True), ("Milan", False)])
    make_question("Capitale de l'Italie ?", [("Rome", True), ("Milan", False)])
    assert older in import_quiz(FILE, "x.txt").questions.all()


def test_same_bytes_are_refused_with_the_quiz_name():
    import_quiz(FILE, "controle.txt")
    with pytest.raises(AlreadyImported) as error:
        preview(FILE, "autre-nom.txt")
    assert str(error.value) == "Fichier déjà importé : QCM « Contrôle »."
    with pytest.raises(AlreadyImported):
        import_quiz(FILE, "autre-nom.txt")
    # Un octet de plus : un autre fichier ; ses questions sont toutes partagées.
    quiz = import_quiz(FILE + b"\n", "controle.txt")
    assert Question.objects.count() == 3
    assert quiz.questions.count() == 3


def test_file_with_nothing_to_import_creates_nothing():
    with pytest.raises(ValueError, match=NOTHING_TO_IMPORT):
        import_quiz(b"*<lines=2> Racontez.\n", "x.txt")
    assert Quiz.objects.count() == 0


def test_syntax_error_creates_nothing():
    with pytest.raises(AmcSyntaxError):
        import_quiz(b"- seule\n", "x.txt")
    assert Quiz.objects.count() == 0


def test_a_question_refused_by_the_form_rolls_everything_back(monkeypatch):
    def refuse(question):
        raise ValueError("refusée")

    monkeypatch.setattr(importer, "create_question", refuse)
    with pytest.raises(ValueError, match="refusée"):
        import_quiz(FILE, "x.txt")
    assert (Quiz.objects.count(), Question.objects.count()) == (0, 0)


def test_long_file_name_is_cut_to_the_field():
    quiz = import_quiz(FILE, "n" * 300 + ".txt")
    assert len(quiz.source_name) == 255


# --- Vues ---------------------------------------------------------------------------------


def upload(client, data: bytes, name: str = "controle.txt"):
    file = SimpleUploadedFile(name, data, content_type="text/plain")
    return client.post(reverse("quiz-import"), {"file": file})


def test_upload_keeps_the_file_until_confirmation(admin_client):
    response = upload(admin_client, FILE)
    pending = PendingImport.objects.get()
    assert response.status_code == 302
    assert response["Location"] == reverse("quiz-import-recap", args=[pending.token])
    assert bytes(pending.data) == FILE and pending.name == "controle.txt"
    assert Quiz.objects.count() == 0
    page = admin_client.get(response["Location"])
    assert page.status_code == 200
    assert "3 questions à importer" in " ".join(page.content.decode().split())


def test_confirmation_imports_once(admin_client):
    url = upload(admin_client, FILE)["Location"]
    response = admin_client.post(url, {"action": "import"})
    quiz = Quiz.objects.get()
    assert response["Location"] == reverse("quiz-detail", args=[quiz.pk])
    assert messages_of(response) == ["QCM importé : 3 questions."]
    assert not PendingImport.objects.exists()
    again = admin_client.post(url, {"action": "import"})  # double clic, autre onglet
    assert again["Location"] == reverse("quiz-import")
    assert messages_of(again) == [EXPIRED]
    assert Quiz.objects.count() == 1


def test_cancel_creates_nothing_and_forgets_the_file(admin_client):
    url = upload(admin_client, FILE)["Location"]
    response = admin_client.post(url, {"action": "cancel"})
    assert response["Location"] == reverse("quiz-list")
    assert messages_of(response) == ["Import annulé."]
    assert not PendingImport.objects.exists()
    assert Quiz.objects.count() == Question.objects.count() == 0


def test_unknown_token_is_expired(admin_client):
    upload(admin_client, FILE)
    for method in ("get", "post"):
        response = getattr(admin_client, method)(reverse("quiz-import-recap", args=["autre"]))
        assert response["Location"] == reverse("quiz-import")
        assert messages_of(response) == [EXPIRED]
    assert Quiz.objects.count() == 0


def test_another_teacher_cannot_open_the_pending_file(admin_client, client, django_user_model):
    url = upload(admin_client, FILE)["Location"]
    other = django_user_model.objects.create_user("collegue", password="x")
    client.force_login(other)
    for method in ("get", "post"):
        response = getattr(client, method)(url, {"action": "import"})
        assert response["Location"] == reverse("quiz-import")
        assert messages_of(response) == [EXPIRED]
    assert Quiz.objects.count() == 0
    assert PendingImport.objects.get().user.username == "admin"


def test_a_new_upload_replaces_the_pending_one(admin_client):
    first = upload(admin_client, FILE)["Location"]
    upload(admin_client, b"* Seconde ?\n+ Oui\n- Non\n", "b.txt")
    assert admin_client.post(first, {"action": "import"})["Location"] == reverse("quiz-import")
    assert Quiz.objects.count() == 0


def test_file_imported_in_the_meantime(admin_client):
    url = upload(admin_client, FILE)["Location"]
    import_quiz(FILE, "controle.txt")  # depuis un autre onglet
    page = admin_client.get(url)
    assert page["Location"] == reverse("quiz-import")
    assert messages_of(page) == ["Fichier déjà importé : QCM « Contrôle »."]
    assert not PendingImport.objects.exists()


def test_confirmation_of_a_file_imported_in_the_meantime(admin_client):
    url = upload(admin_client, FILE)["Location"]
    import_quiz(FILE, "controle.txt")
    response = admin_client.post(url, {"action": "import"})
    assert response["Location"] == reverse("quiz-import")
    assert messages_of(response) == ["Fichier déjà importé : QCM « Contrôle »."]
    assert Quiz.objects.count() == 1


def test_refused_file_shows_the_reasons_on_the_form(admin_client):
    response = upload(admin_client, b"Couleur: bleu\n* Q ?\n+ Oui\n- Non\n")
    assert response.status_code == 200
    assert response.context["form"].non_field_errors() == ["Ligne 1 : option inconnue « Couleur »"]
    assert not PendingImport.objects.exists()


def test_too_large_file_is_refused_without_reading_it_all(admin_client):
    data = b"# " + b"x" * MAX_BYTES + b"\n* Q ?\n+ Oui\n- Non\n"
    response = upload(admin_client, data)
    assert response.context["form"].non_field_errors() == [
        "Fichier trop volumineux : 1 Mo au plus."
    ]


def test_windows_file_with_bom_is_imported_as_sent(admin_client):
    data = "﻿Title: Été\r\n* Q ?\r\n+ Oui\r\n- Non\r\n".encode()
    url = upload(admin_client, data)["Location"]
    admin_client.post(url, {"action": "import"})
    quiz = Quiz.objects.get()
    assert quiz.title == "Été"
    assert quiz.source_sha256 == importer.sha256(data)
