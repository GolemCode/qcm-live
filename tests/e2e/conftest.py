"""Fixtures de bout en bout : vrai serveur (live_server) et vrais navigateurs (Playwright).

- `page` : le PC de l'enseignant qui projette (1920 x 1080).
- `new_phone()` : un nouveau téléphone (Pixel 7 émulé : écran, tactile, user-agent).
"""

import os
from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, expect

# Playwright (API synchrone) tourne dans une boucle asyncio : Django doit l'accepter
# pour que les fixtures puissent toucher la base depuis le thread de test.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

# Délai d'attente des actions Playwright (30 s par défaut) : un échec doit remonter vite.
ACTION_TIMEOUT_MS = 5_000

TEACHER_USERNAME = "prof"
TEACHER_PASSWORD = "mot-de-passe-de-test"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1920, "height": 1080}, "locale": "fr-FR"}


@pytest.fixture(autouse=True)
def _fast_failures(context: BrowserContext) -> None:
    context.set_default_timeout(ACTION_TIMEOUT_MS)


@pytest.fixture
def teacher(transactional_db, django_user_model):
    return django_user_model.objects.create_user(TEACHER_USERNAME, password=TEACHER_PASSWORD)


@pytest.fixture
def new_phone(browser: Browser, playwright: Playwright) -> Iterator[Callable[[], Page]]:
    contexts = []

    def make() -> Page:
        context = browser.new_context(**playwright.devices["Pixel 7"], locale="fr-FR")
        context.set_default_timeout(ACTION_TIMEOUT_MS)
        contexts.append(context)
        return context.new_page()

    yield make
    for context in contexts:
        context.close()


@pytest.fixture
def teacher_page(page: Page, live_server, teacher) -> Page:
    """Le PC de l'enseignant, connecté à son espace."""
    login(page, live_server.url)
    expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()
    return page


def assert_fits_width(page: Page, *, mobile: bool = False) -> None:
    """Aucun défilement horizontal. Sur téléphone, vérifie en plus que la mise en page mobile
    est active (largeur CSS du téléphone, et non 980 px de bureau dézoomés).

    On compare à clientWidth et non à window.innerWidth : Chromium mobile dézoome un contenu
    trop large, et innerWidth grandit alors avec lui, ce qui masquerait le débordement.
    """
    scroll_width, client_width = page.evaluate(
        "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
    )
    assert scroll_width <= client_width, f"débordement : {scroll_width} > {client_width} px"
    if mobile:
        assert client_width < 500, f"mise en page mobile inactive ({client_width} px)"


def login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/prof/")
    page.get_by_label("Identifiant").fill(TEACHER_USERNAME)
    page.get_by_label("Mot de passe").fill(TEACHER_PASSWORD)
    page.get_by_role("button", name="Se connecter").click()
