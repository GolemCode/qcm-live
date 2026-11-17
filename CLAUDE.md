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
- Côté enseignant (I13) : `install.sh` / `install.ps1` installent ; la commande `qcm-live` (`config/launcher.py`) sauvegarde puis lance le mode classe, avec `sauvegarder`, `restaurer [archive]` et `compte`. Essai local : `QCM_LIVE_ARCHIVE=<tar.gz> HOME=<dossier jetable> sh install.sh`. Le guide de l'enseignant est `GUIDE.md` ; le README s'adresse au développement.
- `make check` : vérification rapide (lint, types, unitaires, intégration). Le hook Stop la lance.
- `make verify` : vérification complète, identique à la CI (y compris E2E, couverture de la spec et couverture du code).
- `make accept INC=n` : tableau des exigences de l'incrément n et des tests qui les vérifient.
- Lancer un test précis : `uv run pytest tests/e2e/test_x.py -k nom`. `UV_ENV_FILE=.env.test` est fourni par `.claude/settings.json` : une clé de test, sans valeur, et jamais la vraie.

## Règles non négociables
1. **Spec d'abord.** Chaque comportement a un identifiant `[XXX-nn] (In)` dans SPEC.md. Chaque identifiant a au moins un test E2E Playwright marqué `@pytest.mark.spec("XXX-nn")` qui échouerait si le comportement était cassé.
2. **Tests d'abord.** Le premier commit d'un incrément contient les tests d'acceptation, rouges. Ils sont écrits avant le code, et l'échec est observé à ce moment-là : on ne le reconstitue jamais après coup (I0, voir REX). L'historique git prouve l'ordre des commits, pas l'ordre d'écriture : ne pas le présenter comme une preuve.
3. **Terminé**, c'est seulement : `make verify` vert, PR à la CI verte, fusionnée dans main, agent `spec-auditor` sans réserve bloquante, SPEC.md et REX.md à jour. Ne jamais l'affirmer avant.
4. **Aucun secret, aucune donnée réelle** dans le dépôt : configuration par variables d'environnement, données de test fictives. gitleaks tourne en pre-commit et en CI.
5. **Simplicité.** Rien hors spec. Toute nouvelle dépendance doit répondre à un besoin concret, consigné dans REX.md. Aujourd'hui l'application dépend de Django, de segno (QR code de jonction, I8), de waitress et de whitenoise (mode classe, I7) ; l'installation de l'enseignant passe par uv, hors de l'application (I13), et sert elle-même la police Atkinson Hyperlegible (`static/fonts/`, licence OFL, I10). En test seulement : zxing-cpp et Pillow décodent le QR code ; axe-core (`tests/e2e/vendor/`, MPL-2.0, I10) contrôle l'accessibilité.
6. **Git.**
   - Jamais de commit ni de push sur `main`, qui est protégée : on passe par une PR.
   - Une branche `inc/<n>-<slug>` par incrément. Les incréments sans exigence portent une lettre : `inc/r-<slug>` et tag `inc-r` pour la correction de l'audit externe, `inc/m-<slug>` et tag `inc-m` pour l'incrément de méthode. Le hook Stop reconnaît les deux formes.
   - Commits Conventional Commits en français (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `ci:`, `chore:`), avec le trailer Co-Authored-By.
   - Fusion par `gh pr merge --merge`, puis tag `inc-<n>`.
   - Jamais de `--no-verify` ni de push forcé. Le hook `guard_bash.py` refuse les formes courantes, pas toutes (`git -c core.hooksPath=…`) : la règle s'applique quand même.
7. **Langue.** Code et identifiants en anglais. Interface, docs, commits et PR en français.
   - **La conversation avec le commanditaire se tient en français, du premier au dernier message**, messages intermédiaires compris, même dans une très longue session (dérive constatée en I0-I4).
   - Les prompts de `/simplify`, `/code-review` et `/security-review` sont en anglais, comme les réponses d'outils : cela ne change pas la langue de mes messages.
   - **Moyens (incrément M), au-delà de cette consigne.** La règle n'a pas suffi : 71 messages sur 75 en anglais en I11 (REX, section M).
     - `"language": "french"` dans `.claude/settings.json` : la consigne passe dans le prompt système. Cela reste une consigne.
     - `.claude/hooks/language.py` : en hook PostToolUse, il m'avertit en cours de tour quand le message qui précède un appel d'outil est en anglais ; en seconde entrée Stop, à part de `stop_check.py`, il renvoie au travail un tour qui contient un message anglais. Il ne laisse passer sans contrôle que l'arrêt qui suit son propre renvoi. **Détection heuristique, après coup** : le message est déjà affiché, et un message court ou mêlé de français peut passer.
     - Si l'un de ces rappels arrive : redire brièvement en français ce que j'annonçais, et continuer en français.
8. **Mémoire.** Le savoir durable va dans ce fichier, dans SPEC.md ou dans REX.md, versionnés, jamais dans la mémoire locale de Claude.
9. **Codes de retour.** Le code de retour d'une vérification (`make check`, `pytest`, `pyright`, `ruff`…) doit rester celui de la commande entière. Un pipe vers `tail`, un `;` puis `echo` ou `|| true` l'effacent : deux incidents (I5, un commit parti avec un test en échec ; I6, `exit 0` annoncé sur 16 erreurs pyright).
   - Enchaîner avec `&&`, ou écrire `set -o pipefail` avant le pipe.
   - Pour relire un journal long : `make verify > log 2>&1; code=$?; tail -25 log; exit $code`.
   - Le hook `guard_bash.py` refuse les formes courantes. Un script à part ou une boucle lui échappe : la règle s'applique quand même.
10. **Dire ce qui garantit quoi.** Dans les docs, distinguer ce qu'un mécanisme impose techniquement de ce qui ne tient qu'à la consigne. Ne jamais écrire « prouve », « garantit » ou « en lecture seule » sans l'avoir vérifié. Un incident rattrapé sur le moment se consigne quand même dans REX.md.

## Procédure d'un incrément
Suivre le skill **`increment`** (`.claude/skills/increment/SKILL.md`).

**Audit borné (incrément M) : deux passages de `spec-auditor` au plus.** Le second ne vérifie que les réserves bloquantes du premier. Ce qui reste ensuite va dans le REX, sous « Réserves ouvertes », sauf une réserve qui touche la justesse des notes ou la séparation énoncé/propositions (AFF-01) : je la corrige et je refais moi-même les contre-épreuves de l'auditeur, sans troisième passage. Rien ne l'impose techniquement : le hook Stop ne voit que la ligne `Audit spec-auditor : <commit>`.

## Architecture (cible)
- `config/` : réglages lus depuis l'environnement, urls, vues transverses (accueil, espace enseignant). On y trouve aussi `forms.py`, les briques communes des formulaires enseignant (`TeacherForm`, `table_field`).
- `bank/` : questions, QCM et barème AMC. Le barème se calcule dans `bank/scoring.py`, un module pur à côté de sa définition, qui porte aussi `LETTERS` (A = indice 0).
  - **Barème par question (I12, BAR-01).** Chaque question porte ses directives AMC (`Question.scoring`, texte, vide = b=1, m=0, v=0) ; une proposition d'une question simple peut porter sa valeur (`Choice.points`). `parse_scoring`, `score(Item, chosen)` et `max_score` reproduisent `AMC::Scoring` (SPEC §3). Le QCM n'a plus de barème.
  - « Aucune de ces réponses n'est correcte » (`none_of_these`, BAN-09) n'est pas une ligne `Choice` : la copie figée l'ajoute en dernière proposition (`none: True`). Ordre fixe : `ordered` (BAN-10).
  - **Import AMC-TXT (I12).** `bank/amc_txt.py`, module pur, reproduit les règles de `plain.pm` d'AMC (SPEC §2 ter) : `parse` renvoie un `ParsedFile` ou lève `AmcSyntaxError` (toutes les erreurs, avec leur ligne). `bank/importer.py` crée les questions par `QuestionForm`, partage celles déjà dans la banque et refuse un fichier déjà importé (`Quiz.source_sha256`). Le fichier attend la confirmation en base (`PendingImport`, une ligne par enseignant, remplacée à chaque envoi), et la confirmation relance l'analyse. Seule la requête qui efface cette ligne importe : un double clic retombe sur « Cet import n'est plus disponible ».
  - `make demo` : commande `bank/management/commands/demo.py`, fichier `demo/qcm-demo.txt`.
- `roster/` : groupes d'étudiants. L'import CSV est lu par `roster/csv_import.py`, un module pur qui porte aussi les limites de longueur, reprises par les modèles.
- `live/` : sessions, créneaux, participants et réponses, avec les modules purs `schedule.py` (rotation) et `results.py` (notation et lignes du CSV).
  - **Au lancement, une session fige une copie du QCM et de la liste du groupe** (SES-03, décision I3). Cette copie est faite par `live/snapshot.py` et décrite par des `TypedDict` (`FrozenQuiz`, `FrozenQuestion`, `FrozenStudent`). On la lit par `session.questions` et `session.students`. Chaque question figée porte son barème (`scoring`), et chaque proposition `points` et `none` ; `live/results.py` en tire l'`Item` du barème.
  - Les réponses désignent cette copie, jamais les lignes `Choice` ou `QuizItem`. Modifier une question supprime et recrée ses propositions (BAN-05), et la supprimer la retire des QCM (BAN-07).
  - De même, un participant garde **son propre exemplaire** du numéro et du nom de l'étudiant. Supprimer un groupe (GRP-03) ne doit effacer aucun résultat de session.
- **Séparation des énoncés et des propositions (I9, AFF-01).** Une photo ne doit jamais contenir une question et ses réponses. Le tableau et son état JSON ne reçoivent que les énoncés, le téléphone et son état JSON que les propositions, en vue d'éviter toute fuite même invisible. Le contexte du tableau ne transmet que le texte de l'énoncé.
- **Déroulement (I4).** `live/schedule.py` est un module pur : groupes de N, un créneau de t secondes par question, rotation (rang + étape) mod n, couleur = `Slot.color(rang)`, mélange stable des propositions.
  - `Session.state(now)` donne la phase (`waiting`, `running`, `ended`) et la position (créneau, temps restant), calculées à partir de `started_at`, sans worker.
  - Le rang de rotation d'un participant vaut le maximum + 1 (0 pour le premier). `Answer` garde, par participant et par question figée, les indices **canoniques** des propositions choisies ; pas de ligne signifie pas de réponse (v). « Effacer ma réponse » (ETU-09) envoie une réponse vide, qui supprime la ligne.
  - **Temps additionnel (I5, TPS-01).** On ne décale jamais `started_at`, ce qui ferait reculer le créneau en cours. `Schedule.extra` donne les secondes ajoutées par créneau, et `position()` s'appuie sur `Schedule.deadlines`, les échéances cumulées.
    - Chaque clic est une ligne `Extension` (session, créneau), créée par `Session.add_time(slot)`. Elle vise le créneau affiché, et un clic arrivé après l'échéance est annulé.
    - Le tableau ne se recharge qu'au changement de groupe : son état JSON donne `slot`, que `board.js` reporte dans le formulaire « +10 s ».
- **Fin et résultats (I6).**
  - La référence d'une question, dans le CSV, est son rang dans le QCM figé (`Q1`…), dans l'ordre du QCM.
  - Les notes ne sont jamais projetées : page « Résultats » à part, disponible seulement une fois la session terminée. Les absents viennent de la liste figée, sans ligne `Participant`.
- **Mode classe (I7).** `config/classroom.py`, lancé par `make classe`.
  - Il fixe l'environnement *avant* de charger les réglages : `DJANGO_DEBUG=0`, `QCM_JOIN_URL` (l'adresse du réseau local) et `QCM_TEACHER_LOCAL_ONLY=1`. Le tableau projette `settings.JOIN_URL` (sinon l'adresse de la requête), et son hôte est ajouté à `ALLOWED_HOSTS`.
  - Puis il applique les migrations et sert l'application avec waitress sur toutes les interfaces. whitenoise sert les fichiers statiques depuis leurs dossiers (`WHITENOISE_USE_FINDERS`), sans `collectstatic`.
  - `config/middleware.py` réserve alors tout `/prof/` (connexion comprise) aux requêtes venues du PC lui-même (`REMOTE_ADDR` de boucle locale ; waitress n'est derrière aucun mandataire).
  - Hors debug, les erreurs des requêtes s'affichent dans le terminal (`LOGGING`). Les pages d'erreur `400`, `403_csrf`, `404` et `500` sont en français.
  - `serve(address, port, before_migrate=, on_ready=)` : port vérifié d'abord (« QCM Live est peut-être déjà lancé »), puis migrations, bandeau du terminal, serveur. Le lanceur s'y branche (sauvegarde, navigateur).
- **Adresses, pare-feu, essai (I13, CLA-02 à CLA-04).**
  - `config/network.py` : énumère les adresses du PC (`ip -j` sous Linux, `ioctl` à défaut ; `Get-NetIPAddress` sous Windows) et les classe (`rank`, pur) : point d'accès ouvert par le PC, route par défaut, adresses privées, cartes virtuelles en dernier. Elles passent aux réglages par `QCM_LAN_ADDRESSES` (JSON) et entrent dans `ALLOWED_HOSTS`.
  - `config/join.py` : adresse projetée (`join_url`) = choix de la page « Réseau », gardé dans le cache en mémoire (un seul processus waitress, perdu au redémarrage), sinon `JOIN_URL`, sinon la requête. Seule une adresse candidate est acceptée. Jetons d'essai du téléphone (`/essai/<jeton>/`, page publique) dans le même cache.
  - `config/firewall.py` : ufw, firewalld, réseau Windows « Public », détectés en lecture seule ; il affiche la commande et ne lance que les sondes `PROBES`. Un test d'intégration le vérifie pour la détection, les conseils et la page « Réseau », sur les lancements par `subprocess`, `os.system` et `os.posix_spawn` ; pas l'annonce du terminal, ni un autre moyen de lancer un programme. **Rien ne l'impose techniquement.**
- **Données de l'enseignant installé (I13).** `QCM_DATA_DIR` (`~/.local/share/qcm-live`, Windows `%LOCALAPPDATA%\qcm-live`, droits 700) contient `app/` (code, remplacé à chaque mise à jour), `venv/`, `db.sqlite3` et `reglages.env` (clé secrète, 600, jamais réécrit). Sans `QCM_DATA_DIR`, rien ne change en développement.
  - `config/install.py` : fin d'installation, commune à Linux et Windows (réglages, migrations ; compte et démonstration `demo --sans-compte` à la première installation seulement ; commande et icône `.desktop`). Sans terminal, réponses par `DJANGO_SUPERUSER_*` et `QCM_LIVE_DEMO`.
  - `config/backup.py` (sans Django) : archives `qcm-live-AAAA-MM-JJ-HHhMMmSSs.zip` dans `~/QCM Live/sauvegardes`, 10 gardées, copie par `sqlite3.backup` ; `extract` refuse ce qui n'est pas une sauvegarde (zip, `db.sqlite3`, intégrité, migration inconnue) avant toute écriture.
- **Présentation (I10, direction « Signalétique »).** Une seule feuille, `static/css/app.css`, bâtie sur des variables (`--ink`, `--paper`, `--signal`, `--color-1`…`--color-6`). Police servie par l'application, jamais par un autre serveur.
  - `base.html` : bandeau noir par blocs (`brand`, `band`), puis `after_header`, `<main>` et `footer` (pied du téléphone, hors de `<main>` pour être `contentinfo`). L'espace enseignant garde sa mise en page jusqu'à I19.
  - Téléphone (I11, VIS-04) : classe `phone` sur `<body>` (accueil compris), logo sans lien, propositions en `label.answer` (classe `chosen` posée par la page puis par `phone.js`, sans dépendre de `:has()`), état de l'envoi et « Effacer ma réponse » dans `.answer-bar`, collée au bas de l'écran (`position: sticky`). Cibles tactiles de 48 px au moins.
  - Tableau : tailles en `em`, sur une base de 1,5 % de la hauteur de l'écran, pour que la même mise en page vaille en 1080 et en 720 lignes. Énoncés en graisse normale, plus grands quand N est petit (classes `n-1`…`n-6`).
  - Barre du temps restant : un `<progress data-countdown>` recalé par `qcm.follow` sur `slot_ms` (durée du créneau, temps ajouté compris), au tableau comme sur le téléphone. Sur le téléphone, un filet d'encre la sépare de la couleur 1, jaune comme elle.
  - Accessibilité : `tests/e2e/a11y.py` (axe-core, contraste de tout texte, parcours au clavier avec focus visible).
- **Jonction (I8, SES-05).** Le tableau en attente projette un QR code vers l'écran de la session (`/s/<code>/`), bâti sur la même adresse que le texte projeté (`settings.JOIN_URL`, sinon l'adresse de la requête). Un test E2E le lit comme un vrai lecteur : capture de l'image, puis décodage (`qr_text` dans `tests/e2e/live_ui.py`).
- **Temps réel.** Polling JSON chaque seconde, sans WebSocket. `static/js/poll.js` expose `qcm.poll`, `qcm.countdown` et `qcm.follow`.
  - Toute requête passe par `qcm.request` : délai d'abandon (une requête perdue ne bloque pas les suivantes) et heure du dernier contact avec le serveur (`qcm.lastContact`), que `qcm.watchConnection` traduit en « Connexion perdue » au bout de 3 s (ETU-11). Le compte à rebours expose son échéance sur l'élément (`qcmDeadline`).
  - **Réseau lent (I11, ETU-10).** `static/js/phone.js` tient la trace des envois : par créneau, la dernière réponse donnée (indices canoniques) et si le serveur l'a confirmée. Elle vit en mémoire et se recopie dans `localStorage` (clé `qcm-live:<code>:<id du participant>`) pour la page suivante. Un seul envoi à la fois, renvoyé chaque seconde jusqu'à l'échéance du téléphone, où les propositions se verrouillent.
  - Avant de déclarer une réponse perdue, le téléphone demande au serveur ce qu'il a reçu : `/s/<code>/reponses/` (`student_answers`, `Participant.answers_by_slot`), des indices par créneau, sans énoncé. Les messages communs avec le serveur (`SAVED`, `CLEARED`, `TOO_LATE`) viennent de `live.views`, par des attributs de la page.
  - Au rechargement, la réponse enregistrée est celle que la page cochait à son arrivée (`defaultChecked`, formulaire en `autocomplete="off"`) : un navigateur qui restaure le formulaire ne doit pas la masquer.
  - Une page qui suit le direct porte, sur `<body>` (bloc `body_attrs`), `data-state-url` et un jeton `data-page` (`waiting`, `running:<groupe>` au tableau, `running:<créneau>` au téléphone, `ended`) ; elle se recharge dès que l'état annonce un autre jeton.
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
  - Imposé : `.gitignore`, outil Read refusé (permission), illisible par les autres comptes (droits 600). Vérifications et CI utilisent `.env.test`, sans valeur, et un test l'impose au mode classe.
  - Détecté, pas empêché : gitleaks en pre-commit (une fois `make setup` fait) et en CI (après le push).
  - Consigne seulement : `guard_bash.py` refuse toute commande qui nomme `.env` en argument ou la charge par `uv run --env-file` (sauf `ls`, `test`, `make`, `uv` sans `--env-file`, `git commit`, `git status`…, dont certaines peuvent le lire), mais pas `python3 -c` ni `bash -c`. Claude Code tourne avec les droits de l'utilisateur.
  - Sandbox de Claude Code évalué et **écarté** (raison et conditions de réévaluation dans le REX). Sans `socat`, il ne démarre pas ; sans `failIfUnavailable`, les commandes tournent alors hors sandbox, sans bloquer. Un test de CLA-01 ne peut pas passer dans un réseau isolé.
- **Le hook Stop vérifie aussi la procédure.** Sur une branche d'incrément, il renvoie au travail une fois par arrêt tant que manquent la section du REX, sa ligne `Audit spec-auditor : <commit>`, la PR ou la fusion. Il revient à chaque arrêt, même sans nouveau commit : l'arrêt de I6 survenait justement après une revue sans commit. S'il se déclenche alors qu'on attend vraiment le commanditaire ou la CI, le redire clairement et s'arrêter. Un rapport de revue n'est jamais un message final. La langue du tour (règle 7) est vérifiée par une autre entrée Stop, `language.py` : désactiver `stop_check.py` ne la retire pas.
- **Agent `spec-auditor` : il n'est pas en lecture seule.** Il a Bash et modifie du code pour ses contre-épreuves, dans un worktree jetable (`isolation: worktree`, `worktree.baseRef: head`). Cette isolation fixe son dossier de départ, sans empêcher un chemin absolu : contrôler après son passage que le dépôt principal n'a pas bougé.
- **Horloge système : elle peut reculer** (REX section R). Sur le PC de développement sous WSL2, elle recule d'environ 1,4 à 2 s toutes les 32 s, parfois davantage (`systemd-timesyncd`). Un test à moins de 2 s de marge y échoue au hasard.
  - `tests/conftest.py::_steady_clock` donne au serveur de test une horloge sans saut. Les tests du mode classe la désactivent : leur serveur, lancé à part, lit l'horloge système, et `jump_to` doit lire la même.
  - Le navigateur décompte avec `performance.now()`, jamais `Date.now()`, mais seulement entre deux interrogations : `qcm.follow` le recale chaque seconde sur le serveur. Le serveur de l'application lit l'horloge système, donc le compteur affiché peut remonter : c'est une question ouverte.
  - Avant d'expliquer un test intermittent, mesurer (sonde horloge murale contre monotone). Une CI verte ne dit rien de ce défaut.
- **Le test de CLA-01 dépend du réseau du PC.** Sans route, le mode classe annonce `127.0.0.1` sur ce PC (ailleurs, il essaie d'abord les adresses non locales), et le test échoue sur cette adresse. Vérifier le réseau avant de chercher ailleurs.
- **SQLite sous la charge d'une classe.** Une transaction ordinaire lit puis demande le verrou d'écriture : si une autre écrit déjà, SQLite refuse aussitôt (« database is locked »), sans attendre. 40 téléphones qui valident leur numéro au même instant donnaient des erreurs 500. D'où `transaction_mode: IMMEDIATE` dans `DATABASES` : ne pas le retirer.
- **Plusieurs pytest dans le dépôt (incrément M).** Avant M, ils partageaient une seule base de test : le hook Stop lançait `make check` pendant un pytest en arrière-plan (I7 : 8 tests en erreur, « no such table » ; I11 : deux fois, dont « readonly database »).
  - **Mécanisme :** chaque processus a sa base, `.test-db-<pid>.sqlite3` (`config/settings.py`). `tests/conftest.py` supprime au démarrage celles dont le processus n'existe plus (pytest tué). Un test lance deux pytest à la fois.
  - **En plus :** le hook Stop ne lance pas `make check` quand un pytest tourne sous le dossier du projet (worktrees placés dessous compris, comme `.claude/worktrees/` ; pas un `git worktree add ../x` ; lu dans `/proc`) : il ne prend pas de processeur aux E2E à faible marge et ne vérifie pas du code en cours de mutation. Il me renvoie attendre la fin du pytest (code 2, une fois par arrêt), et le contrôle se fait à un arrêt suivant. Sans `/proc`, ce garde ne voit rien.
  - Rendre la main pendant un pytest en arrière-plan n'est donc plus dangereux pour la base, mais le code n'est alors pas contrôlé : attendre sa fin au premier plan et lire son résultat (`tail --pid=<pid> -f /dev/null`).
- **Tests du mode classe** (`tests/e2e/test_i7_classroom.py`).
  - Ils lancent `make classe` dans un autre processus, sur la base de test (`DJANGO_DB_PATH`), et non `live_server`.
  - Ce serveur ne connaît pas le hachage MD5 des tests : le module redéfinit `_fast_password_hasher` pour hacher comme en production.
- **Un navigateur connecté le reste d'un lancement à l'autre** (I13) : les cookies ne dépendent pas du port, et la clé secrète comme la session en base survivent à une mise à jour ou à une restauration. Un test qui relance le serveur ne retrouve donc pas la page de connexion.
- **Lancer pyright avant chaque commit de code**, pas seulement à `make check` : pre-commit ne lance que ruff (I13 : un commit parti avec quatre erreurs de types).
- Playwright en mode synchrone et pytest-django : il faut `DJANGO_ALLOW_ASYNC_UNSAFE=true`, déjà réglé dans `tests/e2e/conftest.py`.
- **Simuler le réseau d'un téléphone (I11).** Utiliser la fixture `networks` de `tests/e2e/test_i11_phone.py` : requêtes coupées (`cut`), retenues puis relâchées (`hold`), ou reçues par le serveur sans que la réponse revienne (`lose`). `set_offline` coupe tout.
  - Toute interception doit cesser avant la fin du test (`unroute_all(behavior="wait")`) : sinon, des avertissements « coroutine never awaited » apparaissent à la fermeture du navigateur.
  - Un `page.evaluate` qui renvoie la promesse d'une requête retenue attend sa fin et bloque le test : lancer la requête sans renvoyer sa promesse.
  - Sur la couleur 1, le fond de la page a la couleur de la barre du temps : une mesure « après la dernière ligne jaune » tombe sur le fond.
- **Base de test SQLite en fichier** (`DATABASES["default"]["TEST"]["NAME"]`), pas en mémoire, un fichier par processus (voir plus haut). En mémoire partagée, un accès concurrent entre le test et le serveur de test échoue aussitôt (« table is locked ») : un test E2E qui écrit en base pendant que les téléphones interrogent le serveur devenait intermittent (1 fois sur 10).
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
