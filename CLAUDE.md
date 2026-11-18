# CLAUDE.md — QCM Live

Relu à chaque appel : règles et pièges seulement, une ligne chacun. L'origine de chacun est dans `rex/pieges.md` ; la conception par module, dans `ARCHITECTURE.md`.

## Le projet
- QCM d'évaluation en direct, en Django : les questions sont projetées, les étudiants répondent sur téléphone.
- **SPEC.md**, référence fonctionnelle, appartient au commanditaire : toute ambiguïté se pose en question, jamais par une invention silencieuse.
- **REX** : index `REX.md`, un fichier par incrément dans `rex/` (`rex/I15.md`…), sans code ; ne relire que ceux qui servent.
- **ARCHITECTURE.md** : lire la partie du module touché avant de le modifier (`grep -n`), pas le fichier entier.
- Procédure d'un incrément : skill **`increment`**.

## Commandes (make ou uv, jamais pip)
- `make setup` installe et crée `.env`, qui contient la vraie clé : **ne jamais le lire**.
- `make run` (développement), `make superuser`, `make demo`, `make classe` (mode classe, `PORT=`, `ADRESSE=`).
- `make check` : lint, types, unitaires, intégration ; le hook Stop le lance.
- `make verify` : tout, comme la CI ; il enregistre son résultat dans `.verify-result.json`.
- `make accept INC=n` (ou `INC=D`, incrément à lettre déclaré dans `[tool.qcm] lettered`) : exigences de l'incrément ; reprend le résultat du dernier `make verify` vert si aucun fichier n'a changé depuis (REX exclu), sinon relance les tests.
- Un test : `uv run pytest tests/e2e/test_x.py -k nom` (`UV_ENV_FILE=.env.test`, sans secret, fourni par `.claude/settings.json`).
- Consommation d'une période : `uv run --no-env-file python scripts/usage.py <début> <fin>` (tokens, appels, temps actif, par agent, compactions).
- Enseignant : `install.sh` / `install.ps1`, commande `qcm-live` (`config/launcher.py`), guide `GUIDE.md` ; essai : `QCM_LIVE_ARCHIVE=<tar.gz> HOME=<dossier jetable> sh install.sh`.

## Règles non négociables
1. **Spec d'abord** : chaque comportement a un `[XXX-nn] (In)` dans SPEC.md et au moins un E2E Playwright `@pytest.mark.spec("XXX-nn")` qui échouerait s'il était cassé.
2. **Tests d'abord** : le premier commit d'un incrément (après un éventuel commit de méthode) contient les tests d'acceptation, rouges ; l'échec s'observe à l'écriture, jamais reconstitué ; git prouve l'ordre des commits, pas celui de l'écriture.
3. **Terminé** = `make verify` vert, CI verte, PR fusionnée, `spec-auditor` sans réserve bloquante, SPEC.md et `rex/I<n>.md` à jour ; jamais avant.
4. **Aucun secret, aucune donnée réelle** dans le dépôt : variables d'environnement, données fictives ; gitleaks en pre-commit et en CI.
5. **Simplicité** : rien hors spec ; toute nouvelle dépendance répond à un besoin concret consigné dans le REX (liste : `ARCHITECTURE.md`).
6. **Git** : jamais de commit ni de push sur `main` ; branche `inc/<n>-<slug>` (`inc/r-…`, `inc/m-…` sans exigence) ; Conventional Commits en français avec Co-Authored-By ; `gh pr merge --merge` puis tag `inc-<n>` ; jamais `--no-verify` ni push forcé (même par `git -c core.hooksPath=…`).
7. **Langue** : code et identifiants en anglais ; interface, docs, commits, PR et **chaque message au commanditaire, intermédiaires compris**, en français. Après un rappel de `language.py`, redire en français et continuer.
8. **Mémoire** : le savoir durable va dans CLAUDE.md, ARCHITECTURE.md, SPEC.md ou `rex/`, versionnés ; jamais dans la mémoire locale.
9. **Codes de retour** : une vérification garde le code de la commande entière ; ni pipe vers `tail`, ni `; echo`, ni `|| true` ; `&&`, `set -o pipefail`, ou `make verify > log 2>&1; code=$?; tail -25 log; exit $code`.
10. **Dire ce qui garantit quoi** : distinguer l'imposé techniquement de la consigne ; jamais « prouve », « garantit », « en lecture seule » sans vérification ; tout incident, même rattrapé, va au REX.
11. **Audit borné** : deux passages de `spec-auditor` au plus, une douzaine de contre-épreuves chacun ; ensuite « Réserves ouvertes », sauf justesse des notes ou AFF-01 (corriger, puis rejouer soi-même les contre-épreuves).

## Invariants de l'application (détail : ARCHITECTURE.md)
- AFF-01 : le tableau et son JSON ne reçoivent que les énoncés, le téléphone et son JSON que les propositions.
- Une session fige au lancement le QCM et la liste du groupe ; réponses et participants désignent cette copie, jamais les lignes de la banque ou du groupe.
- On ne décale jamais `started_at` : le temps ajouté passe par `Extension`.
- CSP stricte : aucun script ni style inline ; le texte s'insère par `textContent`.
- L'étudiant est désigné par son n° de liste, jamais par son numéro étudiant (ni projeté, ni montré au téléphone).
- Les notes ne sont jamais projetées.

## Pièges connus
- `.env` : imposé = `.gitignore`, Read refusé, droits 600 ; détecté = gitleaks ; consigne seulement = `guard_bash.py` (contourné par `python3 -c`, `bash -c`).
- Sandbox de Claude Code écarté : sans `socat` il ne démarre pas, et sans `failIfUnavailable` les commandes tournent hors sandbox.
- Hook Stop : renvoie au travail une fois par arrêt tant que manquent `rex/I<n>.md`, sa ligne `Audit spec-auditor : <commit>`, la PR ou la fusion ; si l'on attend vraiment le commanditaire ou la CI, le dire et s'arrêter.
- Un rapport de revue n'est jamais un message final : le traiter et enchaîner.
- `spec-auditor` n'est pas en lecture seule (Bash, worktree jetable, chemin absolu possible) : après lui, `git status` vide, même HEAD, `git worktree list` sans copie.
- Horloge sous WSL2 : recule d'environ 2 s toutes les 32 s ; marge de test ≥ 2 s ; mesurer (murale contre monotone) avant d'expliquer un test intermittent.
- Test de CLA-01 : sans route réseau, le mode classe annonce `127.0.0.1` et le test échoue ; vérifier le réseau d'abord.
- SQLite : garder `transaction_mode: IMMEDIATE` (sinon « database is locked » sous 40 téléphones).
- Une base de test par processus pytest ; le hook Stop ne lance pas `make check` pendant un pytest ; attendre un pytest d'arrière-plan au premier plan (`tail --pid=<pid> -f /dev/null`).
- Base de test SQLite en fichier, jamais en mémoire partagée (« table is locked »).
- Tests du mode classe : `make classe` dans un autre processus, horloge système (`_steady_clock` désactivée), hachage de production.
- Un navigateur connecté le reste d'un lancement du serveur à l'autre.
- Lancer pyright avant chaque commit de code : pre-commit ne lance que ruff.
- Commits enchaînés par `&&`, jamais `;` (un commit refusé laisse ses fichiers indexés).
- pre-commit met de côté les fichiers non indexés : une configuration entre dans le même commit que le code qui en dépend.
- ruff : ajouter toute nouvelle application à `known-first-party` avant d'écrire ses tests.
- `gh pr edit` échoue (gh 2.45) : `gh api -X PATCH repos/GolemCode/qcm-live/pulls/<n> -F body=@f.md` ; `gh pr ready <n>` fonctionne.
- CI : jamais `playwright install --with-deps` (11 min sur un miroir lent).
- Typage : `django-stubs` ; relations inverses déclarées sous `if TYPE_CHECKING:`.
- Playwright synchrone avec pytest-django : `DJANGO_ALLOW_ASYNC_UNSAFE=true` (déjà dans `tests/e2e/conftest.py`).
- Fixtures E2E : `page` (tableau, 1920x1080), `teacher_page` (enseignant connecté), `new_phone()` (Pixel 7).
- Préconditions des tests par `tests/factories.py` (formulaires de l'application) ; une création testée passe par l'interface (`tests/e2e/bank_ui.py`).
- Temps en test : `rewind` / `jump_to` ; au moins un test en temps réel par exigence de temps ; attendre le jeton `data-page` d'un téléphone, jamais un délai fixe.
- Téléphone : plusieurs secondes de marge avant une échéance, il peut sauter un créneau placé à 1 s.
- Réseau du téléphone simulé : fixture `networks` (`test_i11_phone.py`) ; `unroute_all(behavior="wait")` avant la fin ; ne pas renvoyer depuis `page.evaluate` la promesse d'une requête retenue.
- `make accept` tout vert ne prouve pas qu'un test vérifie : ce sont les contre-épreuves qui le montrent.
- CSV : neutraliser toute cellule *de texte* commençant par `=`, `+`, `-`, `@` (`results.neutralised`), jamais un nombre.
- Tests de refus aux limites : le cas refusé et le cas tout juste accepté ; relire défauts et valeurs vides après enregistrement.
- `TeacherForm` : `label_suffix` vide ; un champ de tableau sans `<label>` passe par `table_field()`.
- Ne pas lire un gros fichier en entier quand un `grep -n` ou une plage suffit ; garder courtes les sorties de tests (`-q`, fin du journal).

# Compact instructions
Le résumé garde :
- le plan de l'incrément en cours, l'étape atteinte du skill `increment`, ce qui reste à faire, et l'heure de départ (mesure de consommation) ;
- l'état du dépôt : branche, derniers commits (empreinte et objet), fichiers modifiés non commités, PR et état de la CI, processus d'arrière-plan en cours (pid, journal) ;
- les décisions du commanditaire, mot pour mot, les questions qui lui sont posées et en attente, et les choix de conception avec leur raison ;
- les réserves (audit, revues, contre-épreuves), ouvertes ou corrigées, les incidents à porter au REX, le modèle et le niveau des revues ;
- le nombre de résumés déjà faits dans la session.

Le résumé peut laisser :
- le contenu des fichiers qu'on peut relire : n'en garder que le chemin et les lignes utiles ;
- les sorties des tests déjà passés : n'en garder que le verdict, et pour un échec non résolu, son message ;
- les diffs déjà commités et le texte des rapports de revue déjà traités : n'en garder que les décisions.
