# QCM Live

Application web de QCM d'évaluation en direct. Les questions sont projetées au tableau depuis le PC de l'enseignant, et les étudiants répondent sur leur téléphone.

> **Enseignant : lisez [GUIDE.md](GUIDE.md).** Il donne l'installation en une commande, le lancement en classe, les sauvegardes et la mise à jour. La suite de ce fichier s'adresse au développement.

- Spécification fonctionnelle : [SPEC.md](SPEC.md)
- Retour d'expérience, incrément par incrément : [REX.md](REX.md)
- Cadre de travail de l'agent de développement (Claude Code) : [CLAUDE.md](CLAUDE.md) et [.claude/](.claude/)

> État : en développement par incréments. `git log --first-parent main` donne une ligne par incrément livré.

## Développement

### Prérequis

- [uv](https://docs.astral.sh/uv/getting-started/installation/), qui installe lui-même Python 3.12 si besoin.
- git.
- `make`, sous Linux, macOS ou WSL. Sous Windows sans make, voir plus bas.

### Installation et lancement

```bash
git clone https://github.com/GolemCode/qcm-live.git
cd qcm-live
make setup        # dépendances, navigateur de test, hooks git, .env local, base de données
make superuser    # crée un compte enseignant (identifiant + mot de passe)
make run          # serveur de développement, http://localhost:8000
```

`make setup` génère `.env` avec une clé secrète aléatoire propre à votre installation. Ce fichier n'est jamais versionné, et seuls `make setup`, `make run`, `make classe`, `make demo` et `make superuser` le lisent. Les vérifications (`make check`, `make verify`, CI) utilisent `.env.test`, versionné et sans valeur : un clone neuf peut tout vérifier sans clé.

Windows sans make (PowerShell) :

```powershell
uv run --no-project python scripts/gen_env.py
uv sync --locked
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py createsuperuser
uv run --env-file .env python manage.py runserver
```

### Mode classe depuis le dépôt : `make classe`

`make classe` (`PORT=8080`, `ADRESSE=192.168.1.23` au besoin) lance le même serveur que la commande `qcm-live` de l'enseignant (`config/classroom.py`), sans sauvegarde ni ouverture du navigateur, avec la base et le `.env` du dépôt :

- serveur de production (waitress), jamais en mode debug ; migrations appliquées au démarrage ;
- le terminal affiche l'adresse des téléphones, les autres adresses du PC avec leur carte, et un éventuel pare-feu avec la commande pour ouvrir le port (jamais lancée) ;
- l'espace enseignant ne s'ouvre que sur ce PC, par `http://localhost:…/prof/` ; on y choisit une autre adresse et on teste un téléphone (page « Réseau »).

Sous Windows sans make : `uv run --env-file .env python -m config.classroom` (options `--port` et `--adresse`). Depuis WSL, l'adresse n'est joignable par les téléphones qu'en réseau « mirrored ».

### Installation de l'enseignant, depuis le dépôt

`install.sh` (Linux) et `install.ps1` (Windows) téléchargent l'archive de `main`. Pour essayer une version locale sans la publier :

```bash
git archive --prefix=qcm-live/ -o /tmp/qcm-live.tar.gz HEAD
HOME=$(mktemp -d) QCM_LIVE_ARCHIVE=/tmp/qcm-live.tar.gz sh install.sh
```

Le code va dans `~/.local/share/qcm-live/app`, l'environnement Python dans `…/venv`, la base et `reglages.env` (clé secrète) à côté ; `config/install.py` termine l'installation, `config/launcher.py` est la commande `qcm-live`.

### Démonstration : `make demo`

La commande crée un compte enseignant `demo`, un groupe « Démo » de six étudiants fictifs et le QCM du fichier [demo/qcm-demo.txt](demo/qcm-demo.txt), au format AMC-TXT. Elle affiche le mot de passe du compte : il change à chaque lancement, et la commande réutilise le groupe et le QCM déjà créés. Si un compte `demo` existe déjà, son mot de passe est remplacé : ne pas donner ce nom à un vrai compte. L'installation de l'enseignant propose la même démonstration, sans le compte (`demo --sans-compte`).

Sous Windows sans make : `uv run --env-file .env python manage.py migrate`, puis `uv run --env-file .env python manage.py demo`.

## Premier cours

Le parcours de l'enseignant (préparer, en classe, après) est dans [GUIDE.md](GUIDE.md). Avant le premier cours, deux risques restent à lever sur place (SPEC.md, §5) : importer un vrai fichier AMC et comparer quelques notes avec celles d'AMC ; tester un téléphone sur le Wi-Fi de la salle (page « Réseau », « Tester avec mon téléphone »).

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
config/     réglages (lus depuis l'environnement), routes, vues transverses, mode classe (classroom.py),
            adresses et pare-feu (network.py, firewall.py), sauvegarde (backup.py),
            commande qcm-live (launcher.py), fin d'installation (install.py)
bank/       banque de questions, QCM, barème AMC (scoring.py : calcul pur),
            import AMC-TXT (amc_txt.py : analyse pure ; importer.py), commande demo
roster/     groupes d'étudiants, import CSV
live/       sessions en direct : QR code de jonction, déroulement, réponses, résultats
templates/  gabarits HTML          static/  CSS et JS, sans script ni style inline
tests/      unit/ · integration/ · e2e/ (Playwright) · spec_trace.py (traçabilité SPEC.md)
            factories.py (données de test fictives, créées via les formulaires)
scripts/    gen_env.py (création du .env local)
demo/       qcm-demo.txt (fichier AMC-TXT fictif de démonstration)
install.sh  install.ps1   installation de l'enseignant (Linux, Windows) ; GUIDE.md, son guide
.claude/    environnement de l'agent : réglages, hooks, procédure d'incrément, auditeur de spec
```
