"""Accès à l'espace enseignant et en-têtes de sécurité, via le client Django."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_teacher_home_requires_login(client):
    response = client.get(reverse("teacher-home"))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


def test_teacher_home_for_logged_in_teacher(client, django_user_model):
    user = django_user_model.objects.create_user("prof", password="mot-de-passe-de-test")
    client.force_login(user)
    response = client.get(reverse("teacher-home"))
    assert response.status_code == 200
    assert "Espace enseignant" in response.text


def test_logout_requires_post(client, django_user_model):
    user = django_user_model.objects.create_user("prof", password="mot-de-passe-de-test")
    client.force_login(user)
    assert client.get(reverse("logout")).status_code == 405


def test_security_headers(client):
    response = client.get(reverse("home"))
    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
