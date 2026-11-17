---
name: increment
description: Procédure complète pour livrer un incrément du projet QCM Live (branche, tests rouges, implémentation, vérifications, revues, REX, PR, CI, fusion, tag). À utiliser au début de chaque incrément et pour vérifier qu'aucune étape n'est oubliée avant de se déclarer terminé.
---

# Livrer un incrément

L'incrément `n` et son contenu sont définis dans SPEC.md (exigences marquées `(In)`). Le REX est un fichier par incrément (`rex/I<n>.md`, index `REX.md`) ; le plan initial est dans `rex/I0.md`.

**Sobriété (I15).** Chaque appel relit tout le contexte : lire par `grep -n` ou par plage plutôt qu'en entier, garder courtes les sorties de tests (`-q`, fin du journal), ne relire du REX que ce qui sert.

## 1. Démarrer
1. `git switch main && git pull`, puis `git switch -c inc/<n>-<slug>`. Noter l'heure de départ (`date -Iseconds`) : elle sert à la mesure de consommation (§6).
2. Relire dans SPEC.md les exigences `(In)`. S'il y a une ambiguïté fonctionnelle, **poser la question** au commanditaire avant de coder.
3. Si l'incrément comporte un choix de conception, passer en plan mode.
4. Passer `[tool.qcm] increment = n` dans `pyproject.toml`.

## 2. Tests d'acceptation, rouges
1. Écrire dans `tests/e2e/test_i<n>_<slug>.py` au moins un test par exigence, marqué `@pytest.mark.spec("XXX-nn")`. Le test reproduit l'usage réel : le tableau sur `page`, les téléphones sur `new_phone()`, de vrais délais courts.
2. Vérifier qu'ils **échouent pour la bonne raison** : `uv run pytest tests/e2e/test_i<n>_*.py`. Ils sont écrits avant le code, et cet échec s'observe à ce moment-là : ne jamais le reconstituer en retirant du code déjà écrit.
3. Commit : `test: tests d'acceptation I<n> (rouges)`.

## 3. Implémenter
- Logique pure dans des modules sans Django (`schedule.py`, `scoring.py`…), avec des tests unitaires exhaustifs.
- Vues et templates sobres, sans JS ni style inline (CSP).
- Une nouvelle dépendance n'est acceptable qu'avec un besoin concret, noté dans `rex/I<n>.md`.
- Des commits atomiques et lisibles (`feat:`, `fix:`, `refactor:`).

## 4. Vérifier
1. `make verify` vert : lint, types, tous les tests, couverture de la spec, couverture du code ≥ 90 %. Il enregistre son résultat avec l'empreinte du dépôt.
2. `make accept INC=n` : toutes les exigences de l'incrément sont **OK**. Il reprend le résultat du dernier `make verify` vert si aucun fichier n'a changé depuis (REX exclu) ; sinon il relance tous les tests. Le lancer donc juste après `make verify`, avant toute autre modification que le REX. Un incrément sans exigence (R) se vérifie avec le dernier numéro livré (`INC=7`).
3. Contrôle visuel : écrire un script de capture Playwright dans le scratchpad, à 1920x1080 et en Pixel 7, puis lire les PNG avec Read. L'interface doit être sobre et lisible de loin.

## 5. Revues
**Le rapport d'un skill de revue n'est jamais un message final** : le traiter, puis enchaîner aussitôt l'étape suivante. En I6, je me suis arrêté sur le rapport de `/security-review`, et le commanditaire a dû me relancer.

**Modèle et niveau des revues** (consigné en I16, après un écart non écrit d'I15) :
- `/simplify` : ses agents peuvent tourner sur Sonnet. Raison : revue de qualité, sans chasse aux bogues ; ses constats sont triés par moi ; elle relit tout le diff, plusieurs fois en parallèle.
- `/code-review` : sur le modèle de la session, au niveau `medium` par défaut ; `high` si l'incrément touche aux notes, à AFF-01, à l'authentification ou aux sessions. Raison : la justesse est aussi gardée par les tests et par `spec-auditor`, qui reste sur le modèle de la session ; en I15, `medium` a trouvé deux vrais défauts.
- **Le modèle et le niveau effectivement employés s'écrivent dans `rex/I<n>.md`**, avec la raison de tout écart à ces défauts, au moment où on les choisit, jamais reconstitués après coup.

1. `/simplify` sur le diff de la branche.
2. `/code-review` sur le diff, au niveau choisi ci-dessus. Si l'incrément touche aux entrées, à l'authentification, aux sessions ou aux réglages : `/security-review`.
3. **Lancer la CI pendant l'audit** (fait de moi-même en I14, inscrit en I15) : pousser la branche et ouvrir la PR en brouillon (`gh pr create --draft`, corps de §7), puis `gh pr checks --watch` en arrière-plan. La CI (environ 7 min) tourne ainsi en même temps que l'audit au lieu de l'attendre ; un échec de CI se corrige comme un constat d'audit.
4. Lancer l'agent **`spec-auditor`** avec : l'incrément n, le commit à auditer, la liste des exigences nouvelles ou modifiées, et la sortie de `make accept INC=n` (il ne la relance pas). Il travaille dans un worktree jetable, **une douzaine de contre-épreuves au plus**, en ne lançant que les tests concernés. **Deux passages au plus** (incrément M) :
   - premier passage : audit ciblé sur les exigences nouvelles ou modifiées ;
   - second passage, facultatif : lui transmettre la liste des réserves bloquantes du premier ; il ne vérifie que celles-là ;
   - ensuite, ce qui reste va dans `rex/I<n>.md`, sous « Réserves ouvertes ». **Exception** : une réserve qui touche la justesse des notes ou la séparation énoncé/propositions (AFF-01) reste bloquante ; la corriger, puis refaire soi-même les contre-épreuves de l'auditeur, sans troisième passage.
5. Contrôler ensuite que le dépôt principal n'a pas bougé : `git status --short` vide, même `HEAD` qu'avant, et `git worktree list` sans copie oubliée.

## 6. Documenter
- **SPEC.md** : y reporter les réponses du commanditaire et les nouvelles précisions, sans changer un identifiant existant.
- **`rex/I<n>.md`**, et sa ligne dans l'index `REX.md` : objectif, problèmes rencontrés, ce qui a bien marché, ce que j'aurais dû savoir dès le départ, choix techniques et leur raison. Sans code.
- **README.md** et **CLAUDE.md** si les commandes ou les règles changent.
- **Consommation** : `uv run --no-env-file python scripts/usage.py <départ> <maintenant>` (tokens, appels, temps actif, par agent, et compactions du contexte avec leur heure), comparée à l'incrément précédent, à compléter après la fusion si besoin. Le nombre de compactions se reporte tel que le script le donne : après un résumé, on ne voit pas ceux qui l'ont précédé.
- **Dans `rex/I<n>.md`, une ligne `Audit spec-auditor : <commit>`**, écrite une fois l'audit fait : le hook Stop la cherche. Une simple mention de l'agent ne compte pas.
- **Ce qui a dérapé va dans le REX**, même rattrapé aussitôt : un commit raté, un arrêt prématuré, une relance du commanditaire.
- **Ne pas surestimer une preuve** : écrire ce qu'un mécanisme garantit et ce qui ne tient qu'à la consigne (CLAUDE.md, règle 10).

## 7. Livrer
1. La PR est ouverte depuis l'audit (§5) : pousser les derniers commits (`git push`), mettre à jour son corps si besoin (API REST, voir CLAUDE.md), puis `gh pr ready <n>`. Titre `Incrément <n> : <titre>` ; corps : exigences couvertes, sortie de `make accept INC=n`, points d'attention, ligne d'attribution.
2. `gh pr checks --watch` en arrière-plan. Si un check échoue, corriger et pousser.
3. CI verte : `gh pr merge --merge`.
4. `git switch main && git pull && git tag inc-<n> && git push origin inc-<n>`.
5. Résumer au commanditaire ce qui est livré, ce qui ne l'est pas et les questions ouvertes.
