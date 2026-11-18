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
