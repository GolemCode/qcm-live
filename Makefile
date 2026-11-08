# Commandes du projet : les mêmes en local, dans le hook Stop de Claude Code et en CI.
# Sous Windows sans make, voir les commandes `uv run` équivalentes dans le README.

# Deux environnements : la vraie clé (.env, local, jamais versionné) ne sert qu'à lancer l'application.
# Les vérifications utilisent .env.test, versionné et sans secret : un clone neuf peut tout vérifier.
ENV_FILE ?= .env
RUN := uv run --env-file $(ENV_FILE)
CHECK_RUN := uv run --env-file .env.test
PYTEST := $(CHECK_RUN) pytest

.DEFAULT_GOAL := help
.PHONY: help setup run classe superuser lint test e2e check verify verify-tests accept

help: ## Liste des commandes
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

.env:
	uv run --no-project --no-env-file python scripts/gen_env.py

setup: .env ## Installe tout : dépendances, navigateur de test, hooks git, base
	uv sync --locked
	uv run --no-env-file playwright install chromium
	uv run --no-env-file pre-commit install
	$(RUN) python manage.py migrate

run: .env ## Serveur de développement (http://localhost:8000)
	$(RUN) python manage.py migrate
	$(RUN) python manage.py runserver

classe: $(ENV_FILE) ## Mode classe : serveur de production, ouvert aux téléphones du réseau local
	$(RUN) python -m config.classroom $(if $(filter command line,$(origin PORT)),--port $(PORT)) $(if $(ADRESSE),--adresse $(ADRESSE))

superuser: .env ## Crée un compte enseignant
	$(RUN) python manage.py createsuperuser

lint: ## Qualité : ruff, format, types, checks Django, migrations à jour
	uv run --no-env-file ruff check .
	uv run --no-env-file ruff format --check .
	uv run --no-env-file pyright
	$(CHECK_RUN) python manage.py check
	$(CHECK_RUN) python manage.py makemigrations --check --dry-run

test: ## Tests rapides : unitaires + intégration
	$(PYTEST) tests/unit tests/integration

e2e: ## Tests de bout en bout (navigateur réel) + contrôle de couverture de la spec
	$(PYTEST) tests/e2e --spec-check

check: lint test ## Vérification rapide (utilisée par le hook Stop)

verify: lint verify-tests ## Vérification complète, identique à la CI

verify-tests: ## Tous les tests + couverture de la spec + couverture du code
	$(PYTEST) --spec-check --cov --cov-report=term-missing $(PYTEST_ARGS)

accept: ## Couverture des exigences d'un incrément : make accept INC=n
	@test -n "$(INC)" || (echo "Usage : make accept INC=n" && exit 2)
	$(PYTEST) --spec-check --spec-inc=$(INC) -q
