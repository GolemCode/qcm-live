"""Incrément 8 : QR code de jonction au tableau (SES-05), plus de QR code en fin de session
(FIN-02).

Le QR code de jonction se lit comme le ferait un vrai téléphone : capture de l'image projetée,
décodage (`qr_text`), puis ouverture de l'adresse décodée sur un autre appareil.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.live_setup import expect_slot, make_live, open_board
from tests.e2e.live_ui import (
    LIVE_MS,
    connected_names,
    identity,
    join_qr,
    phones_joined,
    qr_text,
    start,
)
from tests.factories import jump_to

MIN_QR_PX = 300  # sur un écran de 1080 lignes : assez grand pour se lire depuis la salle


@pytest.mark.spec("SES-05")
def test_board_qr_code_opens_the_session_on_a_phone(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(1, shown=1)
    open_board(page, live_server.url, session)

    scanned = qr_text(join_qr(page))
    assert scanned == f"{live_server.url}/s/{session.code}/"
    box = join_qr(page).bounding_box()
    assert box and min(box["width"], box["height"]) >= MIN_QR_PX, box
    # L'adresse et le code restent lisibles, pour un téléphone qui ne lit pas le QR code.
    hint = page.get_by_text(re.compile(r"^Sur votre téléphone, ouvrez "))
    expect(hint).to_contain_text(f"{live_server.url}/")
    expect(hint).to_contain_text(session.code)

    # Le téléphone arrive directement sur l'écran de la session : il n'y a plus que le numéro.
    phone = new_phone()
    phone.goto(scanned)
    expect(phone.get_by_label("Code de session")).to_have_count(0)
    phone.get_by_label("Numéro d'étudiant").fill("00123")
    phone.get_by_role("button", name="Valider").click()
    expect(identity(phone)).to_have_text("Vous êtes DURAND Élise")
    expect(connected_names(page)).to_have_text(["DURAND Élise"], timeout=LIVE_MS)

    # Un téléphone déjà identifié qui relit le QR code retrouve son écran, sans nouvelle saisie.
    phone.goto(scanned)
    expect(identity(phone)).to_have_text("Vous êtes DURAND Élise")
    expect(phone.get_by_label("Numéro d'étudiant")).to_have_count(0)


@pytest.mark.spec("SES-05")
def test_join_qr_code_is_gone_once_started(teacher_page: Page, live_server):
    page = teacher_page
    session = make_live(2, shown=1)
    open_board(page, live_server.url, session)
    expect(join_qr(page)).to_be_visible()

    start(page)
    expect(join_qr(page)).to_have_count(0)
    expect(page.get_by_role("img")).to_have_count(0)
    page.reload()
    expect(page.get_by_role("timer", name="Temps restant")).to_be_visible()
    expect(page.get_by_role("img")).to_have_count(0)

    jump_to(session, 61)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    expect(page.get_by_role("img")).to_have_count(0)


@pytest.mark.spec("FIN-02")
def test_phone_only_says_the_session_is_over(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(2, shown=1, seconds=30)
    (phone,) = phones_joined(new_phone, live_server.url, session.code, ["00123"])
    open_board(page, live_server.url, session)
    start(page)
    expect_slot(phone, 0)
    jump_to(session, 61)  # la fin arrive seule, sans recharger à la main

    main = phone.get_by_role("main")
    expect(main).to_contain_text("Session terminée", timeout=LIVE_MS)
    # Ni QR code, ni réponses, ni note : le code de la session et la fin, rien d'autre.
    expected = re.compile(rf"^\s*Session {session.code}\s+Session terminée\.\s*$")
    expect(main).to_have_text(expected)
    expect(phone.get_by_role("img")).to_have_count(0)

    phone.reload()  # téléphone rechargé, ou sorti de veille
    expect(main).to_have_text(expected)
    expect(phone.get_by_role("img")).to_have_count(0)

    stranger = new_phone()  # téléphone non identifié
    stranger.goto(f"{live_server.url}/s/{session.code}/")
    expect(stranger.get_by_role("main")).to_have_text(expected)
    expect(stranger.get_by_role("img")).to_have_count(0)
