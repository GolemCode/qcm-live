# ID — Démonstration complète (DEM-03 à DEM-08, CNT-05)

## Revues
**Modèle et niveau, choisis et consignés avant de lancer.**
- Les agents de `/simplify` tournent sur **Sonnet**. C'est une revue de qualité, dont je trie moi-même les constats.
- `/code-review` tourne sur le modèle de la session (Opus), au niveau **`high`**. L'incrément crée des sessions, des participants et des réponses (la session passée), et lance le serveur sur une autre base que celle de l'enseignant.
- Pas de `/security-review` : l'incrément n'ajoute aucune entrée de l'utilisateur. Les fichiers de `demo-complet/` sont ceux du dépôt, et la commande n'a pas d'argument.

**`/simplify`** (quatre agents Sonnet). Deux constats corrigés :
- `serve(database=)` : le chemin de la base entre par `serve`, qui prépare tout l'environnement avant de charger Django. Avant, `serve_demo` écrivait lui-même dans `os.environ`.
- Réponses de la session passée créées en une seule requête (`bulk_create`) : environ 0,4 s de moins sur les 1,6 s de la préparation, mesurées par l'agent.

Écartés, avec leur raison :
- Chemin de la démonstration non paramétrable (`--demo` en simple drapeau) : `DEMO_DB=` est l'interface du test d'acceptation de `make demo-complete`. Le garde-fou par le nom, `demo.sqlite3`, ne coûte que quelques lignes.
- Options de `demo` en `parents=` d'argparse : il faudrait aussi `SUPPRESS` et des défauts posés après l'analyse ; ce n'est pas plus simple. Le test unitaire couvre les trois places des options.
- `revise` qui relit `QuestionForm(instance)` : c'est la saisie que l'enseignant verrait, renvoyée par le même formulaire. Les champs sont des textes et des booléens, sans liste. Si le formulaire change, le test de DEM-07 échoue.
- Horodatages reculés par `update()` : `start(passé)` est le mécanisme de l'application, et seuls trois champs `auto_now` restent. Un `now` simulé dans la commande serait plus lourd.
- Aides de la démonstration (`demo_account`, `folder_archive`) importées d'un module de commande de `bank` : le couplage est réel, mais ne concerne que deux commandes de démonstration.
- Étiquettes d'incrément opaques dans la traçabilité : elles changeraient la méthode du commit 0780066, hors de cet incrément.
- Noms fictifs un par ligne : c'est ruff format qui les met ainsi ; une chaîne découpée dépasserait 100 colonnes.

**`/code-review` (Opus, `high`)** : dix constats, sans passe de vérification. Corrigés :
- `make accept INC=ID` passait au vert : depuis que les lettres sont admises, un incrément mal tapé ne désignait aucune exigence, et « aucune manquante » valait succès. Désormais, `normalise` n'accepte qu'un numéro ou une seule lettre, et `accept` refuse, avec le code 2, un incrément sans exigence dans SPEC.md. Le défaut venait de ma propre modification de la traçabilité ; aucun test ne couvrait ce cas d'erreur.
- Le garde-fou de `git push` refusait le tag `inc-d` : `TAG_REF` ne connaissait que `inc-<n>` et `inc-r`. Il admet désormais une lettre ; les tests unitaires couvrent `inc-d`, et le refus de `inc-dd`, `inc-d1` et `v1`. Sans la revue, je ne l'aurais découvert qu'au tag, après la fusion.
- `qcm-live demo` mourait sur une trace Python dans deux cas : une base qui n'est pas `demo.sqlite3` (`DEMO_DB=` mal choisi) ; une base encore ouverte sous Windows. Il affiche maintenant un message en français et sort avec le code 1.
- `pick` : un étudiant qui n'avait rien coché répondait « Aucune de ces réponses » avec la probabilité de son niveau, même quand cette réponse était fausse. Les meilleurs donnaient donc le plus souvent une réponse fausse. Désormais, il la choisit à bon escient avec la probabilité de son niveau.
- Les réponses de la session passée étaient toutes datées de « début + 5 min », donc avant le créneau de leur question. Chacune est désormais datée du milieu de son créneau.
- `revise` aurait laissé de côté un champ valant 0, puisque `0 in (None, False, "")` est vrai.

Écartés :
- Deux démonstrations lancées en même temps sur deux ports, depuis le même dossier : sous Linux, la seconde efface la base de la première. Seules des données fictives sont en jeu, recréées au lancement suivant. Sous Windows, le cas est désormais signalé. Un verrou de fichier portable coûterait plus que le risque.
- Année du groupe de 70 étudiants, prise à la date du jour, alors que la session passée remonte à 7 jours. Entre le 1er et le 7 septembre, cette session tombe dans l'année précédente. L'année en cours reste la valeur par défaut (GRP-04), et ce décalage ne touche que l'affichage de la démonstration.
- `import_group` en double avec la démonstration légère, `folder_archive` et `previous_year` recopiés dans le test. Les deux groupes n'ont ni le même format de numéros ni la même taille. Quant aux copies dans le test, elles sont voulues : le test ne réutilise pas le code qu'il vérifie.
- La ligne de D dans l'index `REX.md` : elle s'ajoute à la fin de l'incrément, comme pour les autres.

## Audit
Audit spec-auditor : a7dfec0

Premier passage seulement. Sur neuf mutations, huit font échouer un test : base du professeur restituée, base non recréée, groupe de la session passée, ordre de la nouvelle version, sources du QCM composé, rouge de `.math-error`. La neuvième, le titre d'un fichier changé, survit aux tests de DEM-04 ; le test de DEM-08 la rattrape, puisque le guide cite ce titre.

**Réserves bloquantes** : aucune.

**Réserves ouvertes, non bloquantes** :
- DEM-04 : les titres exacts des trois fichiers ne sont vérifiés que par le parcours du guide (DEM-08), pas par un test de DEM-04.
- DEM-06 : le CSV n'est vérifié que par son en-tête (« note /20 ») et son nombre de lignes, pas par les valeurs des notes. Le calcul de ces notes est couvert par les tests de RES, que l'incrément ne touche pas.

Ce que l'auditeur a vérifié sans mutation, à la lecture : la base n'est jamais sauvegardée. C'est vrai par construction, puisque `save_now` ne copierait que la base des réglages, devenue `demo.sqlite3`.

**Limite** : le test vérifie que la base de l'enseignant n'est ni modifiée ni effacée. Il ne verrait pas une simple ouverture en lecture. Le code n'en fait aucune : `serve` change `DJANGO_DB_PATH` avant de charger Django.

## Objectif
Une démonstration complète, entièrement fictive, que l'enseignant lance à part pour découvrir l'application en dix minutes, sans jamais mettre de fausses sessions dans sa base. Au passage : IMP-09 (import LaTeX) repasse « à confirmer », I18 est mis de côté, et le guide explique les formules qui s'affichent en rouge (CNT-05).

## Décisions du commanditaire
- « Base à part (Recommandé) » : `qcm-live demo` (en développement, `make demo-complete`) lance le serveur sur `demo.sqlite3`, recréée à chaque lancement ; compte « demo » avec un mot de passe affiché dans le terminal ; la base du professeur n'est jamais ouverte.
- « Garder masquées (Recommandé) » : dans la démonstration aussi, la page Résultats s'ouvre notes masquées.

## Choix techniques
- **Préparation par les formulaires de l'application** : import (`import_quiz`), `GroupImportForm`, `LaunchSessionForm`, `AnswerForm`, `QuizForm`, `QuestionForm.save_version`, `Session.enrol` et `start`. La démonstration montre ainsi ce que l'enseignant obtiendrait lui-même, et une règle ajoutée à un formulaire s'y applique aussi. Seuls les horodatages sont reculés après coup.
- **Graine fixe** : les mêmes noms, les mêmes absents et les mêmes notes à chaque lancement (testé). Seuls la date de la session passée et le mot de passe changent.
- **`demo-complet/` à côté de `demo/`** : l'archive de la démonstration légère met tout `demo/` en ZIP, et trois fichiers de plus y cassaient le test d'I12.
- **Base désignée par `serve(database=)`** : le chemin entre dans `DJANGO_DB_PATH` avant `django.setup()`, en même temps que le reste de l'environnement. `reset_demo` refuse tout autre nom que `demo.sqlite3`. C'est un garde-fou dans le code, testé : `DEMO_DB=` du Makefile ne peut pas désigner la base de l'enseignant.
- **Commande d'installation inchangée** : elle ne propose toujours que la démonstration légère (testé).
- Aucune dépendance nouvelle.

## Incidents et écarts
- **Tests corrigés après le commit rouge**, chacun parce qu'il supposait à tort l'interface :
  - « Marquer » agit sur toute la banque ;
  - le libellé « Inclure » est un texte simple ;
  - l'en-tête du CSV est en minuscules ;
  - une note peut être négative ;
  - les fichiers sont déplacés dans `demo-complet/`.
  Aucune assertion n'a été affaiblie : seuls les sélecteurs et les chemins ont changé.
- **Deux tests verts dès le commit rouge**, et c'était attendu : la non-régression de l'installation (DEM-03), et le récapitulatif en rouge de CNT-05, déjà livré en I17. Pour CNT-05, la nouveauté est le guide, dont le test était bien rouge.
- **`pkill -f "config.classroom --demo"`** a tué le shell qui le lançait (code 144), parce que sa propre ligne de commande contenait le motif. Le serveur s'est bien arrêté. À l'avenir : `pgrep`, puis `kill <pid>`.
- **`uv run --no-env-file pytest`** échoue : pytest a besoin de `.env.test`, que `--no-env-file` écarte. Cette option ne vaut que pour ruff, pyright et le script de consommation.
- **Pipe sans `pipefail`**, refusé par le garde-fou, et relancé correctement. **Hook Stop** : un pytest d'arrière-plan s'attend au premier plan (`tail --pid`).
- **Mon script de captures** a cliqué « Marquer » sans choisir de groupe. Refait.
- **`make accept INC=ID` passait au vert** (constat de `/code-review`, corrigé). En admettant les lettres, j'avais rendu possible un incrément sans aucune exigence, et « rien ne manque » valait succès. J'aurais dû tester le cas d'erreur en même temps que le cas nominal.
- **Le garde-fou refusait le tag `inc-d`** (constat de `/code-review`, corrigé). Les incréments à lettre avaient été ajoutés à la traçabilité et aux hooks de session et d'arrêt, mais pas à celui de `git push`. Leçon : quand on étend une notion (ici, l'incrément à lettre), chercher tous ses usages (`grep -rn "inc-"`), pas seulement ceux que l'on modifie.
- **Suivi de la CI coupé** : `gh pr checks --watch` s'est arrêté sur une connexion réinitialisée, avec le code 1, alors que la CI tournait toujours. Un code d'échec du suivi ne prouve pas un échec de la CI : consulter `gh run list`, puis suivre le run lui-même avec `gh run watch <id> --exit-status`.
- **Remarque sur I17, vue aux captures** : dans la liste de confirmation du lancement, l'image d'une question s'affiche en grand. À reprendre dans un prochain incrément.

## Consommation
Mesure : `uv run --no-env-file python scripts/usage.py 2026-11-18T06:45:20+01:00 2026-11-18T07:45:35+01:00`, prise avant la fusion. La PR, la CI finale et le tag n'y sont pas. Cette mesure ne couvre que la dernière partie de la session : la rédaction des tests, des fichiers AMC et du code l'a précédée, avant les résumés que le script ne voit plus.

| | I17 | D (fin de session) |
|---|---|---|
| Tokens | 46,6 M | 25,5 M |
| Appels | 423 | 254 |
| Temps actif | 1,9 h | 1,0 h |
| Contexte principal | 41,1 M (330 appels) | 20,8 M (181 appels) |
| spec-auditor | 34 appels, 1,7 M | 24 appels, 1,0 M |
| Revues (agents `general-purpose`) | 55 appels, 3,6 M | 49 appels, 3,7 M |
| Résumés du contexte | 7 | 3 dans la période (6 h 55, 7 h 05, 7 h 26) |

Les trois fichiers AMC (20 à 30 questions chacun) et le guide ont rempli le contexte vite. La revue en `high` a de nouveau trouvé de vrais défauts, dont deux qui auraient bloqué la livraison elle-même (faux vert de `make accept`, tag refusé).
