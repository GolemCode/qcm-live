"""Groupes : réservés à l'enseignant connecté ; suppression uniquement en POST."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from roster.models import StudentGroup
from tests.factories import make_group

pytestmark = pytest.mark.django_db


@pytest.fixture
def group():
    return make_group("TD", [("1", "A"), ("2", "B")])


@pytest.mark.parametrize("method", ["get", "post"])
def test_anonymous_is_redirected_to_login(client, group, method):
    urls = [
        reverse("group-list"),
        reverse("group-import"),
        reverse("group-detail", args=[group.pk]),
        reverse("group-delete", args=[group.pk]),
    ]
    for url in urls:
        response = getattr(client, method)(url)
        assert response.status_code == 302, url
        assert response["Location"].startswith(reverse("login")), url
    assert StudentGroup.objects.count() == 1


def test_get_on_delete_only_asks_for_confirmation(admin_client, group):
    assert admin_client.get(reverse("group-delete", args=[group.pk])).status_code == 200
    assert StudentGroup.objects.count() == 1


def test_import_without_file_is_refused(admin_client):
    response = admin_client.post(reverse("group-import"), {"name": "TD2"})
    assert "file" in response.context["form"].errors
    assert not StudentGroup.objects.filter(name="TD2").exists()


def test_concurrent_duplicate_name_is_a_form_error_not_a_crash(admin_client, group, monkeypatch):
    """Double clic : le même nom peut passer la validation deux fois avant l'écriture."""
    from roster.forms import GroupImportForm

    monkeypatch.setattr(GroupImportForm, "validate_unique", lambda self: None)
    upload = SimpleUploadedFile("g.csv", b"1;A\n", content_type="text/csv")
    response = admin_client.post(reverse("group-import"), {"name": "TD", "file": upload})
    assert response.status_code == 200
    assert response.context["form"].errors["name"] == ["Un groupe porte déjà ce nom."]
    assert StudentGroup.objects.count() == 1
