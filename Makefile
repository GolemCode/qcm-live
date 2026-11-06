# Commandes du projet : les mêmes en local, dans le hook Stop de Claude Code et en CI.
# Sous Windows sans make, voir les commandes `uv run` équivalentes dans le README.

RUN := uv run --env-file .env
PYTEST := $(RUN) pytest

.DEFAULT_GOAL := help
.PHONY: help setup run superuser lint test e2e check verify verify-tests accept

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

superuser: .env ## Crée un compte enseignant
	$(RUN) python manage.py createsuperuser

lint: .env ## Qualité : ruff, format, types, checks Django, migrations à jour
	uv run --no-env-file ruff check .
	uv run --no-env-file ruff format --check .
	uv run --no-env-file pyright
	$(RUN) python manage.py check
	$(RUN) python manage.py makemigrations --check --dry-run

test: .env ## Tests rapides : unitaires + intégration
	$(PYTEST) tests/unit tests/integration

e2e: .env ## Tests de bout en bout (navigateur réel) + contrôle de couverture de la spec
	$(PYTEST) tests/e2e --spec-check

check: lint test ## Vérification rapide (utilisée par le hook Stop)

verify: lint verify-tests ## Vérification complète, identique à la CI

verify-tests: .env ## Tous les tests + couverture de la spec + couverture du code
	$(PYTEST) --spec-check --cov --cov-report=term-missing $(PYTEST_ARGS)

accept: .env ## Couverture des exigences d'un incrément : make accept INC=n
	@test -n "$(INC)" || (echo "Usage : make accept INC=n" && exit 2)
	$(PYTEST) --spec-check --spec-inc=$(INC) -q
