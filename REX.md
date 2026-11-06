# REX — Retour d'expérience

Ce document doit permettre de refaire le projet de zéro. Il décrit ; il ne contient pas de code. Chaque incrément a la même structure : objectif, problèmes rencontrés, ce qui a bien marché, ce que j'aurais dû savoir dès le départ, choix techniques et leur raison.

---

## I0 — Cadrage et socle

### Objectif
Avant toute fonctionnalité :
- lever les ambiguïtés de la spec ;
- choisir l'environnement de travail ;
- poser un socle où « terminé » se prouve par une commande et par la CI, pas par une affirmation.

Seuls livrables fonctionnels : la page d'accueil et la connexion enseignant, juste de quoi faire tourner la chaîne complète. Le chemin va des tests en vrai navigateur à la CI, puis à la fusion protégée.

### Démarche de cadrage
- **Questions avant le code.** Douze ambiguïtés, posées en trois séries de questions fermées avec une recommandation chaque fois ; les réponses sont dans SPEC.md §6. Les plus structurantes :
  - Comment N questions à l'écran se combinent avec une seule couleur par téléphone. Réponse : groupes de N et rotation synchronisée.
  - Le contenu du QR code. Un QR lisible ne peut pas contenir des énoncés, il contient donc des références.
  - L'identification par une liste fournie, d'où la notion de groupes importés en CSV.
  - L'hébergement : local d'abord.
- **Lire les réponses de près.** Deux réponses étaient en « autre » et changeaient le modèle :
  - « reprendre la logique d'Auto Multiple Choice » pour le barème : j'ai lu la documentation AMC pour proposer le sous-ensemble b, m, v, p ;
  - « un numéro associé depuis une liste fournie » : d'où une question supplémentaire sur la provenance de la liste.
- **Hypothèses écrites.** Les points secondaires que j'ai tranchés moi-même (H1 à H9) sont listés pour validation au lieu d'être imposés en silence. Ils ont été validés avec le plan.
- **Risques remontés.** L'usurpation de numéro, les données personnelles dans un dépôt public, l'isolation des Wi-Fi d'école.

### Environnement retenu (et pourquoi)
- **Reproductibilité.**
  - uv, avec un lockfile et Python 3.12 figé : une seule commande `make setup`.
  - Le Makefile est l'unique point d'entrée, partagé par le développeur, le hook Stop et la CI.
- **Preuve de correction.**
  - Chaque exigence de SPEC.md a un identifiant et un incrément.
  - Un plugin pytest maison (`tests/spec_trace.py`) fait échouer la vérification si une exigence livrée n'a pas de test E2E *réussi*. Un test sauté ou désélectionné ne compte pas.
  - Les tests E2E tournent en vrai Chromium contre un vrai serveur : un contexte bureau pour le tableau, des contextes Pixel 7 pour les téléphones.
- **Garde-fous de session**, en hooks Claude Code versionnés et eux-mêmes testés :
  - formatage et lint à chaque édition ;
  - refus de `--no-verify`, du push forcé, du commit et du push sur main, de la lecture de `.env` ;
  - `make check` obligatoire avant de rendre la main ;
  - un état du projet affiché au démarrage, déduit de git.
- **Hors session.**
  - CI GitHub en deux checks requis : `quality` (gitleaks sur tout l'historique, ruff, pyright, checks Django) et `tests` (tous les tests, spec, couverture ≥ 90 %).
  - `main` protégée avec `enforce_admins`.
  - Fusions par merge commit uniquement, pour qu'une ligne de `--first-parent` corresponde à un incrément.
- **Secrets.**
  - La clé Django n'existe que dans `.env`, généré localement ; en CI, une clé éphémère est générée à chaque run.
  - gitleaks tourne en pre-commit et en CI.
  - GitHub assure le secret scanning et la push protection. Les alertes Dependabot sont activées.
- **Continuité.** `CLAUDE.md` contient les règles et les pièges. Le skill `increment` décrit la procédure pas à pas, et l'agent `spec-auditor` fait un audit adversarial des tests. La mémoire locale de Claude n'est pas utilisée, car elle n'est pas versionnée.

### Écarté (et pourquoi)
- **Temps réel.** Pas de WebSockets ni de Channels, Redis, Celery ou htmx : un polling JSON et des échéances en base suffisent pour une classe.
- **Données et environnement.** Pas de PostgreSQL : SQLite suffit. Pas de Docker : uv suffit. Pas de python-dotenv : l'option `--env-file` de uv fait le même travail.
- **Plugins Claude Code.** Écartés :
  - Playwright MCP, redondant avec Playwright en Python et la lecture des captures ;
  - security-guidance, une revue LLM non déterministe à chaque tour, qui double gitleaks et `/security-review` ;
  - context7, github MCP et serena ;
  - les plugins de workflow, qui doublent les skills intégrés.
- **`django-types`.** Retiré en cours de route (voir Problèmes).
- **Plugin `pyright-lsp`.** Écarté après essai (voir Problèmes).

### Problèmes rencontrés
- **`django-types` ne connaît pas Django 6.** pyright ne trouvait pas `django.utils.csp`, la CSP native de Django 6. Sans ces stubs, pyright infère depuis le code source de Django, sans aucune erreur. Ils sont donc retirés.
- **Plugin `pyright-lsp`.** Il lance `pyright-langserver` depuis le PATH, alors que le binaire est dans `.venv/bin` : sans environnement activé, rien ne démarre. Il faudrait une installation globale, non reproductible depuis le dépôt. Pyright reste donc en ligne de commande dans `make check`, ce qui revient au même contrôle au moment du hook Stop.
- **Le garde-fou `.env` s'est déclenché à tort sur une de mes commandes.** Un `.` en fin de ligne a été pris pour la commande `source`, et l'expression régulière a trouvé `.env` plusieurs lignes plus loin, dans un heredoc. La règle est désormais limitée à une ligne, et ce cas est un test de non-régression.
- **pytest-base-url**, dépendance de pytest-playwright, émet un avertissement de dépréciation sous pytest 9. Il est filtré précisément, par son message.
- **Le hook gitleaks de pre-commit n'analyse que les fichiers indexés.** Il ne voit rien avec `--all-files`. En CI, j'utilise donc le binaire gitleaks, à la version et à l'empreinte SHA-256 figées, sur tout l'historique.

- **Un commit au message faux, rattrapé avant le push.**
  - Trois commits de correction enchaînés avec `;` ont été refusés par pre-commit : la règle ruff qu'ils nécessitaient était dans `pyproject.toml`, que pre-commit avait mis de côté parce qu'il n'était pas indexé.
  - Leurs fichiers sont restés indexés, et le commit suivant les a emportés sous un message qui ne décrivait qu'une partie du contenu.
  - Comme rien n'était poussé, les commits ont été refaits dans le bon ordre, configuration d'abord.
  - Règle ajoutée à CLAUDE.md : enchaîner les commits avec `&&`, et vérifier le contenu de chaque commit (`git log --stat`) avant de pousser.

### Ce que les revues ont trouvé
La CI était verte. Les deux revues ont pourtant trouvé de vrais défauts, ce qui justifie de les garder dans la procédure.
- **Agent `spec-auditor`.** Le test de GEN-01 ne prouvait rien sur téléphone.
  - Chromium mobile dézoome un contenu trop large, et `window.innerWidth` grandit alors avec lui. Le contrôle « pas de défilement horizontal » passait donc même avec un débordement de 4 fois la largeur de l'écran, ou sans balise viewport.
  - Correction : comparer à `clientWidth`, vérifier que la largeur reste celle d'un téléphone, et ajouter un test qui prouve que le contrôle sait échouer.
  - Contre-épreuve faite : la suppression de la balise viewport fait désormais échouer GEN-01.
- **`/code-review`.** 10 constats, tous corrigés :
  - En CI, le lockfile n'était pas vraiment strict : une commande `uv run` exécutée avant `uv sync --locked` re-verrouillait en silence. Correction : `UV_LOCKED=1` sur tout le workflow, et génération du `.env` avec `--no-project`.
  - Le hook Stop ignorait les modifications des fichiers non suivis, donc un nouveau fichier cassé passait. Il échouait aussi dans un worktree, où `.git` est un fichier.
  - Le garde Bash par expressions régulières était à la fois contournable (`git -C . commit -n`, `SKIP=`, refspec `+`, `git push origin HEAD` depuis main, commandes sur plusieurs lignes) et trop strict (texte d'un message de commit, `main-hotfix`). Il est réécrit par analyse des arguments (shlex), et chaque cas est devenu un test.
  - La traçabilité identifiait les tests par leur seul nom : collision possible entre deux fichiers.
  - Le test de déconnexion pouvait être instable : il n'attendait pas la fin de la navigation.
  - Quatre réglages Django ne faisaient que répéter les valeurs par défaut.

### Ce qui a bien marché
- **Tester que le contrôle sait échouer.** La traçabilité a été essayée sur un incrément futur (`make accept INC=1`, en échec) et avec un test désélectionné (en échec). Un filet qui n'a jamais attrapé de faute ne prouve rien.
- **Vérifier gitleaks pour de vrai.** Un jeton factice, dans un dépôt jetable hors projet, a bien été bloqué.
- **Des hooks testés comme du code.** Le premier déclenchement à tort a été corrigé avec un test.

### Ce que j'aurais dû savoir dès le départ
- Les stubs tiers de Django prennent du retard sur les versions majeures : vérifier la compatibilité avant de les retenir.
- Les plugins LSP de Claude Code supposent un binaire dans le PATH, ce qui s'accorde mal avec un environnement virtuel de projet.
- Avec Playwright en API synchrone et pytest-django, il faut `DJANGO_ALLOW_ASYNC_UNSAFE`.
- Le hook gitleaks de pre-commit ne remplace pas une analyse de l'historique.
- **Mesurer la largeur en émulation mobile.** Ne jamais comparer à `window.innerWidth`, à cause du dézoom automatique ; utiliser `documentElement.clientWidth`.
- **Garde-fous de commandes shell.** Un filtre par expressions régulières sur le texte brut est à la fois contournable et trop strict. Il faut raisonner sur les arguments, et traiter le retour à la ligne comme un séparateur de commandes.
- **Une CI verte ne suffit pas.** Une relecture adversariale, faite par un agent avec un contexte neuf, trouve des tests creux que la CI ne peut pas voir.

### Choix techniques et leur raison
- **Django 6.1** : la CSP native permet une politique stricte sans dépendance. Python 3.12 est le minimum requis.
- **Aucune dépendance d'exécution autre que Django à ce stade.** segno, waitress et whitenoise n'arriveront qu'avec les incréments qui en ont besoin.
- **Réglages par variables d'environnement.** Le démarrage échoue sans clé secrète, avec un message qui dit quoi faire.
- **Pas de Django admin.** Il est hors spec ; la connexion enseignant utilise uniquement `django.contrib.auth`.
- **Tests d'acceptation d'abord**, commités rouges en tête de chaque incrément : l'historique prouve qu'ils peuvent échouer.

### Plan des incréments suivants
| Inc | Contenu |
|---|---|
| I1 | Banque de questions (simples et multiples), QCM ordonnés, barème AMC |
| I2 | Groupes d'étudiants par import CSV |
| I3 | Lancement de session, accueil au tableau, l'étudiant rejoint avec son numéro |
| I4 | Déroulement : groupes, couleurs, rotation, chronomètre, réponses, retardataires |
| I5 | +10 secondes |
| I6 | Fin : QR code, résultats, export CSV |
| I7 | Mode classe : serveur de production local, E2E contre ce serveur |
| I8 | Hébergement en ligne (conditionnel, selon la décision du professeur) |

---

## I1 — Banque de questions, QCM et barème

### Objectif
- L'enseignant crée, modifie et supprime des questions, simples ou multiples, de 2 à 8 propositions.
- Il compose des QCM : une sélection ordonnée de questions de la banque, une même question pouvant servir dans plusieurs QCM.
- Il règle pour chaque QCM un barème à la manière d'Auto Multiple Choice (b, m, v, p).

### Questions posées à la commanditaire
- **Modifier et supprimer.** La spec dit « définir », sans plus. Réponse : créer, modifier et supprimer, d'où les nouvelles exigences BAN-05 à BAN-08.
- **Plancher `p` et non-réponse.** `p` relève-t-il aussi `v` ? Réponse : non, `p` ne borne que la somme des cases.
- **Décision prise sans poser la question.** Un QCM contient au moins une question : un QCM vide ne peut pas se lancer. C'est écrit dans BAN-03 et signalé dans la PR.

### Problèmes rencontrés
- **pyright inutilisable sans stubs Django.**
  - Sans eux, il voit les champs de modèle comme des `DecimalField`, alors qu'à l'exécution ce sont des `Decimal`.
  - `django-types`, écarté en I0, ne suit toujours pas Django 6. En revanche, `django-stubs` 6.1 suit Django 6.1 et marche avec pyright.
  - Il reste à déclarer les relations inverses sous `TYPE_CHECKING`.
  - J'ai aussi découvert que le dossier de l'application n'était pas dans le périmètre de pyright : un outil de contrôle mal configuré passe en silence.
- **pre-commit refusait la migration générée.**
  - Appelé sur des chemins explicites, ruff ignore ses exclusions sans `--force-exclude`. C'est le défaut déjà corrigé dans le hook Claude en I0, qui restait dans pre-commit.
  - Leçon : quand on corrige un mécanisme, chercher ses autres copies.
- **Une suite de tests trop lente.** Deux causes :
  - les préconditions passaient toutes par l'interface ;
  - le hachage PBKDF2 coûte environ 0,3 s à chaque création de compte ou connexion.

  Correctifs : préconditions créées en base, hachage MD5 en test. La suite passe de 27,6 s à 11 s.
- **Un tableau de couverture vert qui ne prouvait pas tout.**
  - L'agent `spec-auditor` a cassé six comportements sans qu'aucun test n'échoue : une question multiple à une seule bonne réponse refusée, le minimum de 2 propositions en multiple, les règles appliquées à la seule création, un plancher vide enregistré à 0, le titre ou l'énoncé vides, un ordre égal à l'inverse de la création.
  - Les tests ont été durcis, puis les 7 contre-épreuves rejouées : toutes sont maintenant détectées.

### Ce qui a bien marché
- **Les tests d'acceptation écrits d'abord, avec des parcours réutilisables** (`bank_ui.py`). Ils ont échoué pour la bonne raison, puis sont passés du premier coup après l'implémentation. Ce succès immédiat était justement suspect, et l'audit l'a confirmé.
- **Quatre revues complémentaires.**
  - `/simplify` : un `ModelForm` au lieu d'un formulaire écrit à la main, une seule source pour les valeurs par défaut.
  - `/code-review` : des messages d'erreur trompeurs, `commit=False` ignoré.
  - `/security-review` : rien trouvé.
  - `spec-auditor` : des tests creux.

  Aucune revue n'a trouvé ce qu'a trouvé une autre.
- **Des fabriques de données qui passent par les formulaires de l'application.** Une précondition ne peut pas créer une donnée que l'interface refuserait.

### Ce que j'aurais dû savoir dès le départ
- **Un test de refus ne prouve pas l'acceptation à la limite.** Pour chaque règle, il faut tester le cas refusé et le cas tout juste accepté, par exemple une question multiple à une seule bonne réponse.
- **Une valeur par défaut doit être relue après enregistrement,** pas seulement dans le formulaire vierge.
- **Un ordre attendu ne doit pas coïncider avec l'ordre de création,** ni avec son inverse.
- **Toute vérification de validité vaut aussi à la modification.**

### Choix techniques et leur raison
- **Sans JavaScript.**
  - L'ordre des questions d'un QCM se saisit par numéros d'ordre ; vide signifie « exclue ».
  - Les 8 emplacements de proposition sont fixes, et les vides sont ignorés.
- **Barème.**
  - Le calcul, en fonctions pures, est dans `bank/scoring.py`, à côté de la définition du barème plutôt que dans `live/`.
  - Les valeurs par défaut viennent d'une source unique (`Scale()`).
  - Les libellés gardent les lettres AMC en minuscules.
- **Modifier une question supprime puis recrée ses propositions.** C'est simple, et sans risque à une condition, inscrite dans CLAUDE.md pour I3/I4 : une session lancée fige une copie de son QCM, et les réponses désignent cette copie, jamais les lignes de la banque.
- **Messages de confirmation (`role="status"`) et erreurs (`role="alert"`) par des mécanismes communs.** Les tests les retrouvent par leur rôle accessible, ce qui vérifie au passage que l'interface est accessible.
- **Nouvelle dépendance de développement : `django-stubs`.** Elle sert au typage statique des modèles ; elle n'est pas embarquée dans l'application.
