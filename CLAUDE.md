# CLAUDE.md — cadre de travail du projet QCM Live

Ce fichier est chargé au début de chaque session Claude Code. Il prime sur les habitudes par défaut.

## Le projet
QCM d'évaluation en direct en Django : les questions sont projetées, les étudiants répondent sur téléphone.
- **SPEC.md** est la référence fonctionnelle. Le fonctionnel appartient à la commanditaire : toute ambiguïté se pose en question, jamais par une invention silencieuse.
- **REX.md** est le retour d'expérience, une section par incrément, sans code.
- Le plan initial (architecture, incréments, environnement) est résumé dans REX.md, section I0.

## Commandes (toujours via make ou uv, jamais pip)
- `make setup` : installation complète. Elle crée `.env`, qui contient des secrets : **ne jamais le lire**.
- `make run` : serveur de développement. `make superuser` : crée un compte enseignant.
- `make check` : vérification rapide (lint, types, unitaires, intégration). Le hook Stop la lance.
- `make verify` : vérification complète, identique à la CI (y compris E2E, couverture de la spec et couverture du code).
- `make accept INC=n` : tableau des exigences de l'incrément n et des tests qui les vérifient.
- Lancer un test précis : `uv run pytest tests/e2e/test_x.py -k nom`. `UV_ENV_FILE=.env` est fourni par `.claude/settings.json`.

## Règles non négociables
1. **Spec d'abord.** Chaque comportement a un identifiant `[XXX-nn] (In)` dans SPEC.md. Chaque identifiant a au moins un test E2E Playwright marqué `@pytest.mark.spec("XXX-nn")` qui échouerait si le comportement était cassé.
2. **Tests d'abord.** Le premier commit d'un incrément contient les tests d'acceptation, rouges.
3. **Terminé**, c'est seulement : `make verify` vert, PR à la CI verte, fusionnée dans main, agent `spec-auditor` sans réserve bloquante, SPEC.md et REX.md à jour. Ne jamais l'affirmer avant.
4. **Aucun secret, aucune donnée réelle** dans le dépôt : configuration par variables d'environnement, données de test fictives. gitleaks tourne en pre-commit et en CI.
5. **Simplicité.** Rien hors spec. Toute nouvelle dépendance doit répondre à un besoin concret, consigné dans REX.md. Aujourd'hui l'application ne dépend que de Django ; segno, waitress et whitenoise arriveront avec les incréments qui en ont besoin.
6. **Git.**
   - Jamais de commit ni de push sur `main`, qui est protégée : on passe par une PR.
   - Une branche `inc/<n>-<slug>` par incrément.
   - Commits Conventional Commits en français (`feat:`, `fix:`, `test:`, `docs:`, `ci:`, `chore:`), avec le trailer Co-Authored-By.
   - Fusion par `gh pr merge --merge`, puis tag `inc-<n>`.
   - Jamais de `--no-verify` ni de push forcé : un hook les refuse.
7. **Langue.** Code et identifiants en anglais. Interface, docs, commits et PR en français.
8. **Mémoire.** Le savoir durable va dans ce fichier, dans SPEC.md ou dans REX.md, versionnés, jamais dans la mémoire locale de Claude.

## Procédure d'un incrément
Suivre le skill **`increment`** (`.claude/skills/increment/SKILL.md`).

## Architecture (cible)
- `config/` : réglages lus depuis l'environnement, urls, vues transverses (accueil, espace enseignant).
- `bank/` : questions, QCM et barème AMC.
- `roster/` : groupes d'étudiants (import CSV).
- `live/` : sessions, créneaux, participants et réponses. On y trouve aussi les modules purs `schedule.py` (rotation), `scoring.py` (barème) et `receipt.py` (contenu du QR).
- Le temps réel passe par un polling JSON d'environ 1 s, sans WebSocket. Le temps est calculé à partir des échéances en base, sans worker. CSP stricte : aucun script ni style inline.
- Tests :
  - `tests/unit` : fonctions pures et hooks ;
  - `tests/integration` : client Django ;
  - `tests/e2e` : Playwright, avec le fixture `page` pour le PC du tableau (1920x1080) et `new_phone()` pour les téléphones (Pixel 7).

## Pièges connus
- Playwright en mode synchrone et pytest-django : il faut `DJANGO_ALLOW_ASYNC_UNSAFE=true`, déjà réglé dans `tests/e2e/conftest.py`.
- `django-types` ne suit pas Django 6 (par exemple `django.utils.csp`) : ces stubs sont retirés, et pyright infère depuis le code source de Django.
