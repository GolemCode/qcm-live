---
name: increment
description: Procédure complète pour livrer un incrément du projet QCM Live (branche, tests rouges, implémentation, vérifications, revues, REX, PR, CI, fusion, tag). À utiliser au début de chaque incrément et pour vérifier qu'aucune étape n'est oubliée avant de se déclarer terminé.
---

# Livrer un incrément

L'incrément `n` et son contenu sont définis dans SPEC.md (exigences marquées `(In)`) et résumés dans REX.md (section I0, plan).

## 1. Démarrer
1. `git switch main && git pull`, puis `git switch -c inc/<n>-<slug>`.
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
- Une nouvelle dépendance n'est acceptable qu'avec un besoin concret, noté dans REX.md.
- Des commits atomiques et lisibles (`feat:`, `fix:`, `refactor:`).

## 4. Vérifier
1. `make verify` vert : lint, types, tous les tests, couverture de la spec, couverture du code ≥ 90 %.
2. `make accept INC=n` : toutes les exigences de l'incrément sont **OK**. Un incrément sans exigence (R) se vérifie avec le dernier numéro livré (`INC=7`).
3. Contrôle visuel : écrire un script de capture Playwright dans le scratchpad, à 1920x1080 et en Pixel 7, puis lire les PNG avec Read. L'interface doit être sobre et lisible de loin.

## 5. Revues
**Le rapport d'un skill de revue n'est jamais un message final** : le traiter, puis enchaîner aussitôt l'étape suivante. En I6, je me suis arrêté sur le rapport de `/security-review`, et le commanditaire a dû me relancer.

1. `/simplify` sur le diff de la branche.
2. `/code-review` sur le diff. Si l'incrément touche aux entrées, à l'authentification, aux sessions ou aux réglages : `/security-review`.
3. Lancer l'agent **`spec-auditor`** avec l'incrément n et le commit à auditer. Il travaille dans un worktree jetable. Il ne doit rester aucune réserve bloquante.
4. Contrôler ensuite que le dépôt principal n'a pas bougé : `git status --short` vide, même `HEAD` qu'avant, et `git worktree list` sans copie oubliée.

## 6. Documenter
- **SPEC.md** : y reporter les réponses du commanditaire et les nouvelles précisions, sans changer un identifiant existant.
- **REX.md**, nouvelle section `I<n>` : objectif, problèmes rencontrés, ce qui a bien marché, ce que j'aurais dû savoir dès le départ, choix techniques et leur raison. Sans code.
- **README.md** et **CLAUDE.md** si les commandes ou les règles changent.
- **Dans la section du REX, une ligne `Audit spec-auditor : <commit>`**, écrite une fois l'audit fait : le hook Stop la cherche. Une simple mention de l'agent ne compte pas.
- **Ce qui a dérapé va dans le REX**, même rattrapé aussitôt : un commit raté, un arrêt prématuré, une relance du commanditaire.
- **Ne pas surestimer une preuve** : écrire ce qu'un mécanisme garantit et ce qui ne tient qu'à la consigne (CLAUDE.md, règle 10).

## 7. Livrer
1. `git push -u origin inc/<n>-<slug>`.
2. `gh pr create`, titre `Incrément <n> : <titre>`. Le corps contient les exigences couvertes, la sortie de `make accept INC=n`, les points d'attention, et se termine par la ligne d'attribution.
3. `gh pr checks --watch` en arrière-plan. Si un check échoue, corriger et pousser.
4. CI verte : `gh pr merge --merge`.
5. `git switch main && git pull && git tag inc-<n> && git push origin inc-<n>`.
6. Résumer au commanditaire ce qui est livré, ce qui ne l'est pas et les questions ouvertes.
