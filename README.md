# QCM Live

Application web de QCM d'évaluation en direct. Les questions sont projetées au tableau depuis le PC de l'enseignant, et les étudiants répondent sur leur téléphone.

- Spécification fonctionnelle : [SPEC.md](SPEC.md)
- Retour d'expérience, incrément par incrément : [REX.md](REX.md)
- Cadre de travail de l'agent de développement (Claude Code) : [CLAUDE.md](CLAUDE.md) et [.claude/](.claude/)

> État : en développement par incréments. `git log --first-parent main` donne une ligne par incrément livré.

## Prérequis

- [uv](https://docs.astral.sh/uv/getting-started/installation/), qui installe lui-même Python 3.12 si besoin.
- git.
- `make`, sous Linux, macOS ou WSL. Sous Windows sans make, voir plus bas.

## Installation et lancement

```bash
git clone https://github.com/GolemCode/qcm-live.git
cd qcm-live
make setup        # dépendances, navigateur de test, hooks git, .env local, base de données
make superuser    # crée un compte enseignant (identifiant + mot de passe)
make run          # http://localhost:8000
```

`make setup` génère `.env` avec une clé secrète aléatoire propre à votre installation. Ce fichier n'est jamais versionné.

### Windows sans make (PowerShell)

```powershell
uv run --no-project python scripts/gen_env.py
uv sync --locked
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py createsuperuser
uv run --env-file .env python manage.py runserver
```

## Vérifier

| Commande | Ce qu'elle vérifie |
|---|---|
| `make check` | lint (ruff), format, types (pyright), checks Django, migrations à jour, tests unitaires et d'intégration |
| `make e2e` | tests de bout en bout dans un vrai navigateur (Chromium), PC du tableau et téléphones émulés |
| `make verify` | tout, comme la CI : y compris la couverture de la spec et celle du code (≥ 90 %) |
| `make accept INC=n` | les exigences de l'incrément n et les tests qui les vérifient |

Chaque exigence de [SPEC.md](SPEC.md) porte un identifiant, par exemple `[ETU-04]`. `make verify` échoue si une exigence déjà livrée n'est vérifiée par aucun test de bout en bout réussi.

La CI GitHub Actions lance les mêmes commandes à chaque PR. Elle analyse aussi tout l'historique git à la recherche de secrets (gitleaks). Il est impossible de fusionner dans `main` sans CI verte.

## Organisation du code

```
config/     réglages (lus depuis l'environnement), routes, vues transverses
bank/       banque de questions, QCM, barème AMC (scoring.py : calcul pur)
templates/  gabarits HTML          static/  un CSS (et un JS à venir), sans script inline
tests/      unit/ · integration/ · e2e/ (Playwright) · spec_trace.py (traçabilité SPEC.md)
            factories.py (données de test fictives, créées via les formulaires)
scripts/    gen_env.py (création du .env local)
.claude/    environnement de l'agent : réglages, hooks, procédure d'incrément, auditeur de spec
```
