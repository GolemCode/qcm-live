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
   - Commits Conventional Commits en français (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `ci:`, `chore:`), avec le trailer Co-Authored-By.
   - Fusion par `gh pr merge --merge`, puis tag `inc-<n>`.
   - Jamais de `--no-verify` ni de push forcé : un hook les refuse.
7. **Langue.** Code et identifiants en anglais. Interface, docs, commits et PR en français.
8. **Mémoire.** Le savoir durable va dans ce fichier, dans SPEC.md ou dans REX.md, versionnés, jamais dans la mémoire locale de Claude.

## Procédure d'un incrément
Suivre le skill **`increment`** (`.claude/skills/increment/SKILL.md`).

## Architecture (cible)
- `config/` : réglages lus depuis l'environnement, urls, vues transverses (accueil, espace enseignant). On y trouve aussi `forms.py`, les briques communes des formulaires enseignant (`TeacherForm`, `table_field`).
- `bank/` : questions, QCM et barème AMC. Le barème se calcule dans `bank/scoring.py`, un module pur à côté de sa définition.
- `roster/` : groupes d'étudiants. L'import CSV est lu par `roster/csv_import.py`, un module pur qui porte aussi les limites de longueur, reprises par les modèles.
- `live/` : sessions, créneaux, participants et réponses, avec les modules purs `schedule.py` (rotation) et `receipt.py` (contenu du QR).
  - **Au lancement, une session fige une copie du QCM et de la liste du groupe** (SES-03, décision I3). Cette copie est faite par `live/snapshot.py` et décrite par des `TypedDict` (`FrozenQuiz`, `FrozenQuestion`, `FrozenStudent`). On la lit par `session.questions` et `session.students`. Le barème figé est sérialisé par `Scale.to_json` ; le lecteur correspondant viendra avec la notation.
  - Les réponses désignent cette copie, jamais les lignes `Choice` ou `QuizItem`. Modifier une question supprime et recrée ses propositions (BAN-05), et la supprimer la retire des QCM (BAN-07).
  - De même, un participant garde **son propre exemplaire** du numéro et du nom de l'étudiant. Supprimer un groupe (GRP-03) ne doit effacer aucun résultat de session.
- **Déroulement (I4).** `live/schedule.py` est un module pur : groupes de N, un créneau de t secondes par question, rotation (rang + étape) mod n, couleur = `Slot.color(rang)`, mélange stable des propositions.
  - `Session.state(now)` donne la phase (`waiting`, `running`, `ended`) et la position (créneau, temps restant), calculées à partir de `started_at`, sans worker.
  - Le rang de rotation d'un participant vaut le maximum + 1 (0 pour le premier). `Answer` garde, par participant et par question figée, les indices **canoniques** des propositions choisies ; pas de ligne signifie pas de réponse (v).
  - **I5 (+10 s).** Ne pas décaler `started_at`, ce qui ferait reculer le créneau en cours. Ajouter à `Schedule` les secondes ajoutées par créneau et faire marcher `position()` sur les échéances cumulées. L'ajout doit être atomique.
- **Temps réel.** Polling JSON chaque seconde, sans WebSocket. `static/js/poll.js` expose `qcm.poll`, `qcm.countdown` et `qcm.follow`.
  - Une page qui suit le direct porte `data-state-url` et un jeton `data-page` (`waiting`, `running:<groupe>` au tableau, `running:<créneau>` au téléphone, `ended`) ; elle se recharge dès que l'état annonce un autre jeton.
  - Le texte est toujours inséré avec `textContent`.
  - CSP stricte : aucun script ni style inline.
- **Identité de l'étudiant.** Elle est stockée dans la session Django : `request.session["live_participants"] = {code: id du participant}`, une identité par appareil et par session. Un numéro déjà pris est refusé par la contrainte d'unicité en base, seul arbitre en cas de concurrence.
- **Saisies numériques sur téléphone** (code, numéro) : utiliser `live.forms.DigitsField`, qui affiche le pavé numérique et ignore les espaces.
- Tests :
  - `tests/unit` : fonctions pures et hooks ;
  - `tests/integration` : client Django ;
  - `tests/e2e` : Playwright, avec le fixture `page` pour le PC du tableau (1920x1080), `teacher_page` pour l'enseignant connecté et `new_phone()` pour les téléphones (Pixel 7).
  - Préconditions des tests :
    - `tests/factories.py` crée les données en passant par les formulaires de l'application, pour qu'aucune donnée ne soit impossible à créer par l'interface ;
    - quand le test vérifie la création elle-même, il passe par l'interface (`tests/e2e/bank_ui.py`).
  - Temps : `tests.factories.rewind(session, s)` avance le déroulement sans attendre, en reculant `started_at` ; `jump_to(session, s)` le place à s secondes du démarrage, pour tester une échéance à la demi-seconde près. Au moins un test par exigence de temps tourne en temps réel (DER-02). Pour attendre qu'un téléphone affiche un créneau, attendre son jeton `data-page`, jamais un délai fixe.

## Pièges connus
- Playwright en mode synchrone et pytest-django : il faut `DJANGO_ALLOW_ASYNC_UNSAFE=true`, déjà réglé dans `tests/e2e/conftest.py`.
- **Base de test SQLite en fichier** (`DATABASES["default"]["TEST"]["NAME"]`), pas en mémoire. En mémoire partagée, un accès concurrent entre le test et le serveur de test échoue aussitôt (« table is locked ») : un test E2E qui écrit en base pendant que les téléphones interrogent le serveur devenait intermittent (1 fois sur 10).
- **Enchaîner les commits avec `&&`, jamais avec `;`.** Un commit refusé par pre-commit laisse ses fichiers indexés, et le commit suivant les emporte sous un message faux.
- **Imports et ruff.** ruff ne classe un import parmi ceux du projet que si le module existe. D'où la liste `known-first-party` dans `pyproject.toml` : y ajouter toute nouvelle application **avant** d'écrire ses tests rouges.
- **`gh pr edit` échoue** avec le `gh` 2.45 de la machine (requête GraphQL sur les « Projects classic » obsolètes). Modifier une PR par l'API REST : `gh api -X PATCH repos/GolemCode/qcm-live/pulls/<n> -F body=@fichier.md`. Pour sortir une PR du brouillon : `gh pr ready <n>`, qui fonctionne. Vérifier le numéro de la PR avant toute modification.
- **CI.** Pas de `playwright install --with-deps` : un miroir apt lent l'a fait durer 11 min. Le runner a déjà les bibliothèques, et le navigateur sans interface est mis en cache.
- pre-commit met de côté les fichiers non indexés : une modification de configuration (`pyproject.toml`) doit entrer dans le même commit que le code qui en dépend, ou avant lui.
- **Typage.**
  - Utiliser `django-stubs`, qui suit Django 6.1 ; `django-types` ne suit pas Django 6.
  - Sans stubs, pyright prend les champs de modèle pour des `DecimalField`, au lieu de `Decimal`.
  - Les relations inverses (`question.choices`) se déclarent sous `if TYPE_CHECKING:` dans le modèle.
- **Un tableau `make accept` tout vert ne prouve pas qu'un test vérifie quelque chose.** Avant la fusion, l'agent `spec-auditor` casse des comportements dans une copie jetable du dépôt et vérifie qu'un test échoue. Reproduire ensuite ces contre-épreuves après correction.
- **Export CSV (I6, RES-02).** Les noms d'étudiants viennent d'un fichier fourni de l'extérieur. Pour qu'un tableur n'exécute pas une formule, neutraliser toute cellule qui commence par `=`, `+`, `-` ou `@`.
- **Tests de refus aux limites.** Pour chaque règle, tester le cas refusé et le cas tout juste accepté. Relire après enregistrement les valeurs par défaut et les valeurs vides.
- **Code bâti sur `TeacherForm`.**
  - Libellés : `label_suffix` vide, sinon le français ajoute « : ».
  - Champ dans un tableau, sans `<label>` visible : l'envelopper dans `table_field()` pour lui donner un nom accessible.
