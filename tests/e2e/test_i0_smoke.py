"""Incrément 0 : accueil et connexion enseignant, dans de vrais navigateurs."""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import TEACHER_PASSWORD, assert_fits_width, login


@pytest.mark.spec("GEN-01")
def test_home_on_projector_and_phone(page: Page, new_phone, live_server):
    page.goto(live_server.url)
    expect(page.get_by_role("heading", name="QCM Live")).to_be_visible()
    assert_fits_width(page)

    phone = new_phone()
    phone.goto(live_server.url)
    expect(phone.get_by_role("heading", name="QCM Live")).to_be_visible()
    assert_fits_width(phone, mobile=True)


def test_fits_width_detects_overflow_on_phone(new_phone):
    """Le contrôle de GEN-01 sait échouer : Chromium mobile dézoome un contenu trop large,
    ce qui masque le débordement si l'on compare à window.innerWidth."""
    phone = new_phone()
    viewport = '<meta name="viewport" content="width=device-width, initial-scale=1">'
    phone.set_content(f'{viewport}<div style="width:600px">trop large</div>')
    with pytest.raises(AssertionError):
        assert_fits_width(phone, mobile=True)
    # Téléphone neuf : la balise viewport d'un set_content précédent resterait active.
    bare = new_phone()
    bare.set_content("<p>page sans balise viewport</p>")
    with pytest.raises(AssertionError, match="mise en page mobile"):
        assert_fits_width(bare, mobile=True)


@pytest.mark.spec("ENS-01")
def test_teacher_login_logout(page: Page, live_server, teacher):
    login_url = re.compile(re.escape(f"{live_server.url}/prof/connexion/") + r"\?next=/prof/$")

    # Sans connexion : redirection vers la page de connexion.
    page.goto(f"{live_server.url}/prof/")
    expect(page).to_have_url(login_url)
    expect(page.get_by_role("heading", name="Connexion enseignant")).to_be_visible()

    # Mauvais mot de passe : refus avec message.
    page.get_by_label("Identifiant").fill(teacher.username)
    page.get_by_label("Mot de passe").fill(TEACHER_PASSWORD + "-faux")
    page.get_by_role("button", name="Se connecter").click()
    expect(page.get_by_role("alert")).to_contain_text("mot de passe")
    expect(page.get_by_role("heading", name="Espace enseignant")).to_have_count(0)

    # Bon mot de passe : accès à l'espace enseignant.
    login(page, live_server.url)
    expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()

    # Déconnexion : retour à l'accueil, puis l'espace enseignant redevient inaccessible.
    page.get_by_role("button", name="Se déconnecter").click()
    expect(page).to_have_url(f"{live_server.url}/")
    page.goto(f"{live_server.url}/prof/")
    expect(page).to_have_url(login_url)
