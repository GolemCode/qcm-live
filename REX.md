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

### Ce qui a bien marché
- **Tester que le contrôle sait échouer.** La traçabilité a été essayée sur un incrément futur (`make accept INC=1`, en échec) et avec un test désélectionné (en échec). Un filet qui n'a jamais attrapé de faute ne prouve rien.
- **Vérifier gitleaks pour de vrai.** Un jeton factice, dans un dépôt jetable hors projet, a bien été bloqué.
- **Des hooks testés comme du code.** Le premier déclenchement à tort a été corrigé avec un test.

### Ce que j'aurais dû savoir dès le départ
- Les stubs tiers de Django prennent du retard sur les versions majeures : vérifier la compatibilité avant de les retenir.
- Les plugins LSP de Claude Code supposent un binaire dans le PATH, ce qui s'accorde mal avec un environnement virtuel de projet.
- Avec Playwright en API synchrone et pytest-django, il faut `DJANGO_ALLOW_ASYNC_UNSAFE`.
- Le hook gitleaks de pre-commit ne remplace pas une analyse de l'historique.

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
