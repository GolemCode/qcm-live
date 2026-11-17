# Règles et pièges de CLAUDE.md : leur origine

Jusqu'à I14, CLAUDE.md donnait pour chaque règle et chaque piège l'incident qui l'avait fait naître. Relu à chaque appel de l'agent (environ 9 000 tokens), il a été réduit en I15 à une ligne par règle et par piège. Le texte complet d'avant I15 est repris ci-dessous, sans changement : c'est l'historique des incidents. Le détail de chacun est dans le REX de son incrément.

## Règles non négociables (texte d'avant I15)
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

## Pièges connus (texte d'avant I15)
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
- **SQLite sous la charge d'une classe.** Une transaction ordinaire lit puis demande le verrou d'écriture : si une autre écrit déjà, SQLite refuse aussitôt (« database is locked »), sans attendre. 40 téléphones qui valident leur numéro (depuis I14 : confirment leur nom) au même instant donnaient des erreurs 500. D'où `transaction_mode: IMMEDIATE` dans `DATABASES` : ne pas le retirer.
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
