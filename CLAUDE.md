# CLAUDE.md — cadre de travail du projet QCM Live

Ce fichier est chargé au début de chaque session Claude Code. Il prime sur les habitudes par défaut.

## Le projet
QCM d'évaluation en direct en Django : les questions sont projetées, les étudiants répondent sur téléphone.
- **SPEC.md** est la référence fonctionnelle. Le fonctionnel appartient au commanditaire : toute ambiguïté se pose en question, jamais par une invention silencieuse.
- **REX.md** est le retour d'expérience, une section par incrément, sans code.
- Le plan initial (architecture, incréments, environnement) est résumé dans REX.md, section I0.

## Commandes (toujours via make ou uv, jamais pip)
- `make setup` : installation complète. Elle crée `.env`, qui contient la vraie clé : **ne jamais le lire**. Rien ne l'empêche techniquement (voir « Secrets » dans les pièges) : cette règle tient à la consigne.
- `make run` : serveur de développement. `make superuser` : crée un compte enseignant.
- `make classe` : mode classe (CLA-01), serveur de production ouvert au réseau local (`PORT=`, `ADRESSE=`).
- `make check` : vérification rapide (lint, types, unitaires, intégration). Le hook Stop la lance.
- `make verify` : vérification complète, identique à la CI (y compris E2E, couverture de la spec et couverture du code).
- `make accept INC=n` : tableau des exigences de l'incrément n et des tests qui les vérifient.
- Lancer un test précis : `uv run pytest tests/e2e/test_x.py -k nom`. `UV_ENV_FILE=.env.test` est fourni par `.claude/settings.json` : une clé de test, sans valeur, et jamais la vraie.

## Règles non négociables
1. **Spec d'abord.** Chaque comportement a un identifiant `[XXX-nn] (In)` dans SPEC.md. Chaque identifiant a au moins un test E2E Playwright marqué `@pytest.mark.spec("XXX-nn")` qui échouerait si le comportement était cassé.
2. **Tests d'abord.** Le premier commit d'un incrément contient les tests d'acceptation, rouges. Ils sont écrits avant le code, et l'échec est observé à ce moment-là : on ne le reconstitue jamais après coup (I0, voir REX). L'historique git prouve l'ordre des commits, pas l'ordre d'écriture : ne pas le présenter comme une preuve.
3. **Terminé**, c'est seulement : `make verify` vert, PR à la CI verte, fusionnée dans main, agent `spec-auditor` sans réserve bloquante, SPEC.md et REX.md à jour. Ne jamais l'affirmer avant.
4. **Aucun secret, aucune donnée réelle** dans le dépôt : configuration par variables d'environnement, données de test fictives. gitleaks tourne en pre-commit et en CI.
5. **Simplicité.** Rien hors spec. Toute nouvelle dépendance doit répondre à un besoin concret, consigné dans REX.md. Aujourd'hui l'application dépend de Django, de segno (QR code, I6), de waitress et de whitenoise (mode classe, I7). En test seulement : zxing-cpp et Pillow décodent le QR code.
6. **Git.**
   - Jamais de commit ni de push sur `main`, qui est protégée : on passe par une PR.
   - Une branche `inc/<n>-<slug>` par incrément (`inc/r-<slug>` et tag `inc-r` pour la correction de l'audit externe).
   - Commits Conventional Commits en français (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `ci:`, `chore:`), avec le trailer Co-Authored-By.
   - Fusion par `gh pr merge --merge`, puis tag `inc-<n>`.
   - Jamais de `--no-verify` ni de push forcé : un hook les refuse.
7. **Langue.** Code et identifiants en anglais. Interface, docs, commits et PR en français.
   - **La conversation avec le commanditaire se tient en français, du premier au dernier message**, messages intermédiaires compris, même dans une très longue session (dérive constatée en I0-I4).
   - Les prompts de `/simplify`, `/code-review` et `/security-review` sont en anglais, comme les réponses d'outils : cela ne change pas la langue de mes messages.
8. **Mémoire.** Le savoir durable va dans ce fichier, dans SPEC.md ou dans REX.md, versionnés, jamais dans la mémoire locale de Claude.
9. **Codes de retour.** Le code de retour d'une vérification (`make check`, `pytest`, `pyright`, `ruff`…) doit rester celui de la commande entière. Un pipe vers `tail`, un `;` puis `echo` ou `|| true` l'effacent : deux incidents (I5, un commit parti avec un test en échec ; I6, `exit 0` annoncé sur 16 erreurs pyright).
   - Enchaîner avec `&&`, ou écrire `set -o pipefail` avant le pipe.
   - Pour relire un journal long : `make verify > log 2>&1; code=$?; tail -25 log; exit $code`.
   - Le hook `guard_bash.py` refuse les formes courantes. Un script à part ou une boucle lui échappe : la règle s'applique quand même.
10. **Dire ce qui garantit quoi.** Dans les docs, distinguer ce qu'un mécanisme impose techniquement de ce qui ne tient qu'à la consigne. Ne jamais écrire « prouve », « garantit » ou « en lecture seule » sans l'avoir vérifié. Un incident rattrapé sur le moment se consigne quand même dans REX.md.

## Procédure d'un incrément
Suivre le skill **`increment`** (`.claude/skills/increment/SKILL.md`).

## Architecture (cible)
- `config/` : réglages lus depuis l'environnement, urls, vues transverses (accueil, espace enseignant). On y trouve aussi `forms.py`, les briques communes des formulaires enseignant (`TeacherForm`, `table_field`).
- `bank/` : questions, QCM et barème AMC. Le barème se calcule dans `bank/scoring.py`, un module pur à côté de sa définition, qui porte aussi `LETTERS` (A = indice 0).
- `roster/` : groupes d'étudiants. L'import CSV est lu par `roster/csv_import.py`, un module pur qui porte aussi les limites de longueur, reprises par les modèles.
- `live/` : sessions, créneaux, participants et réponses, avec les modules purs `schedule.py` (rotation), `receipt.py` (contenu du QR) et `results.py` (notation et lignes du CSV).
  - **Au lancement, une session fige une copie du QCM et de la liste du groupe** (SES-03, décision I3). Cette copie est faite par `live/snapshot.py` et décrite par des `TypedDict` (`FrozenQuiz`, `FrozenQuestion`, `FrozenStudent`). On la lit par `session.questions` et `session.students`. Le barème figé est sérialisé par `Scale.to_json` et relu par `Scale.from_json`.
  - Les réponses désignent cette copie, jamais les lignes `Choice` ou `QuizItem`. Modifier une question supprime et recrée ses propositions (BAN-05), et la supprimer la retire des QCM (BAN-07).
  - De même, un participant garde **son propre exemplaire** du numéro et du nom de l'étudiant. Supprimer un groupe (GRP-03) ne doit effacer aucun résultat de session.
- **Déroulement (I4).** `live/schedule.py` est un module pur : groupes de N, un créneau de t secondes par question, rotation (rang + étape) mod n, couleur = `Slot.color(rang)`, mélange stable des propositions.
  - `Session.state(now)` donne la phase (`waiting`, `running`, `ended`) et la position (créneau, temps restant), calculées à partir de `started_at`, sans worker.
  - Le rang de rotation d'un participant vaut le maximum + 1 (0 pour le premier). `Answer` garde, par participant et par question figée, les indices **canoniques** des propositions choisies ; pas de ligne signifie pas de réponse (v). « Effacer ma réponse » (ETU-09) envoie une réponse vide, qui supprime la ligne.
  - **Temps additionnel (I5, TPS-01).** On ne décale jamais `started_at`, ce qui ferait reculer le créneau en cours. `Schedule.extra` donne les secondes ajoutées par créneau, et `position()` s'appuie sur `Schedule.deadlines`, les échéances cumulées.
    - Chaque clic est une ligne `Extension` (session, créneau), créée par `Session.add_time(slot)`. Elle vise le créneau affiché, et un clic arrivé après l'échéance est annulé.
    - Le tableau ne se recharge qu'au changement de groupe : son état JSON donne `slot`, que `board.js` reporte dans le formulaire « +10 s ».
- **Fin et résultats (I6).**
  - La référence d'une question, dans le QR code comme dans le CSV, est son rang dans le QCM figé (`Q1`…). Le reçu suit l'ordre de la rotation (`Participant.receipt`), le CSV l'ordre du QCM.
  - Les notes ne sont jamais projetées : page « Résultats » à part, disponible seulement une fois la session terminée. Les absents viennent de la liste figée, sans ligne `Participant`.
  - Un test E2E lit le QR code comme un vrai lecteur : capture de l'image, puis décodage (`qr_text` dans `tests/e2e/live_ui.py`).
- **Mode classe (I7).** `config/classroom.py`, lancé par `make classe`.
  - Il fixe l'environnement *avant* de charger les réglages : `DJANGO_DEBUG=0`, `QCM_JOIN_URL` (l'adresse du réseau local) et `QCM_TEACHER_LOCAL_ONLY=1`. Le tableau projette `settings.JOIN_URL` (sinon l'adresse de la requête), et son hôte est ajouté à `ALLOWED_HOSTS`.
  - Puis il applique les migrations et sert l'application avec waitress sur toutes les interfaces. whitenoise sert les fichiers statiques depuis leurs dossiers (`WHITENOISE_USE_FINDERS`), sans `collectstatic`.
  - `config/middleware.py` réserve alors tout `/prof/` (connexion comprise) aux requêtes venues du PC lui-même (`REMOTE_ADDR` de boucle locale ; waitress n'est derrière aucun mandataire).
  - Hors debug, les erreurs des requêtes s'affichent dans le terminal (`LOGGING`). Les pages d'erreur `400`, `403_csrf`, `404` et `500` sont en français.
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
- **Secrets : ce qui protège vraiment `.env`** (audit externe, REX section R).
  - Imposé : hors du dépôt (`.gitignore`, gitleaks), outil Read refusé (permission), illisible par les autres comptes (droits 600). Vérifications et CI utilisent `.env.test`, sans valeur.
  - Consigne seulement : `guard_bash.py` refuse les lectures courantes mais pas `python3 -c`. Claude Code tourne avec les droits de l'utilisateur.
  - Sandbox de Claude Code évalué et **écarté** (raison et conditions de réévaluation dans le REX). Sans `socat`, il ne démarre pas ; sans `failIfUnavailable`, les commandes tournent alors hors sandbox, sans bloquer. Un test de CLA-01 ne peut pas passer dans un réseau isolé.
- **Le hook Stop vérifie aussi la procédure.** Sur une branche d'incrément, il renvoie au travail une fois par arrêt tant que REX, audit, PR ou fusion manquent. S'il se déclenche alors qu'on attend vraiment le commanditaire ou la CI, le redire clairement et s'arrêter. Un rapport de revue n'est jamais un message final.
- **Agent `spec-auditor` : il n'est pas en lecture seule.** Il a Bash et modifie du code pour ses contre-épreuves, dans un worktree jetable (`isolation: worktree`, `worktree.baseRef: head`). Cette isolation fixe son dossier de départ, sans empêcher un chemin absolu : contrôler après son passage que le dépôt principal n'a pas bougé.
- **SQLite sous la charge d'une classe.** Une transaction ordinaire lit puis demande le verrou d'écriture : si une autre écrit déjà, SQLite refuse aussitôt (« database is locked »), sans attendre. 40 téléphones qui valident leur numéro au même instant donnaient des erreurs 500. D'où `transaction_mode: IMMEDIATE` dans `DATABASES` : ne pas le retirer.
- **Ne jamais rendre la main pendant un `make verify` en arrière-plan** : le hook Stop lance `make check`, donc un second pytest sur la même base de test (I7 : 8 tests en erreur, « no such table »). Lancer `make verify` au premier plan.
- **Tests du mode classe** (`tests/e2e/test_i7_classroom.py`).
  - Ils lancent `make classe` dans un autre processus, sur la base de test (`DJANGO_DB_PATH`), et non `live_server`.
  - Ce serveur ne connaît pas le hachage MD5 des tests : le module redéfinit `_fast_password_hasher` pour hacher comme en production.
- Playwright en mode synchrone et pytest-django : il faut `DJANGO_ALLOW_ASYNC_UNSAFE=true`, déjà réglé dans `tests/e2e/conftest.py`.
- **Jamais deux exécutions de pytest en parallèle dans le même dépôt** : elles partagent la base de test en fichier (« no such table »). Un agent qui fait des contre-épreuves travaille dans un worktree jetable.
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
- **Export CSV (I6, RES-02).** Les noms d'étudiants viennent d'un fichier fourni de l'extérieur. Pour qu'un tableur n'exécute pas une formule, neutraliser toute cellule *de texte* qui commence par `=`, `+`, `-` ou `@` (`results.neutralised`). Ne pas l'appliquer aux nombres calculés : une note négative commence par `-`.
- **Laisser au téléphone le temps de voir un créneau.** Il interroge l'état chaque seconde et se recharge avec un délai de 0 à 300 ms. Placer le déroulement à 1 s d'une échéance peut lui faire sauter le créneau (test intermittent en I6) : garder plusieurs secondes de marge, puis avancer.
- **Tests de refus aux limites.** Pour chaque règle, tester le cas refusé et le cas tout juste accepté. Relire après enregistrement les valeurs par défaut et les valeurs vides.
- **Code bâti sur `TeacherForm`.**
  - Libellés : `label_suffix` vide, sinon le français ajoute « : ».
  - Champ dans un tableau, sans `<label>` visible : l'envelopper dans `table_field()` pour lui donner un nom accessible.
