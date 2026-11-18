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
