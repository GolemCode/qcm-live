"""Incrément 0 : accueil et connexion enseignant, dans de vrais navigateurs."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import TEACHER_PASSWORD, login


def _has_no_horizontal_scroll(page: Page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.spec("GEN-01")
def test_home_on_projector_and_phone(page: Page, new_phone, live_server):
    page.goto(live_server.url)
    expect(page.get_by_role("heading", name="QCM Live")).to_be_visible()
    assert _has_no_horizontal_scroll(page)

    phone = new_phone()
    phone.goto(live_server.url)
    expect(phone.get_by_role("heading", name="QCM Live")).to_be_visible()
    assert phone.viewport_size is not None and phone.viewport_size["width"] < 500
    assert _has_no_horizontal_scroll(phone)


@pytest.mark.spec("ENS-01")
def test_teacher_login_logout(page: Page, live_server, teacher):
    # Sans connexion : redirection vers la page de connexion.
    page.goto(f"{live_server.url}/prof/")
    expect(page.get_by_role("heading", name="Connexion enseignant")).to_be_visible()

    # Mauvais mot de passe : refus avec message.
    page.get_by_label("Identifiant").fill(teacher.username)
    page.get_by_label("Mot de passe").fill(TEACHER_PASSWORD + "-faux")
    page.get_by_role("button", name="Se connecter").click()
    expect(page.get_by_role("alert")).to_be_visible()
    expect(page.get_by_role("heading", name="Espace enseignant")).to_have_count(0)

    # Bon mot de passe : accès à l'espace enseignant.
    login(page, live_server.url)
    expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()

    # Déconnexion : l'espace enseignant redevient inaccessible.
    page.get_by_role("button", name="Se déconnecter").click()
    page.goto(f"{live_server.url}/prof/")
    expect(page.get_by_role("heading", name="Connexion enseignant")).to_be_visible()
