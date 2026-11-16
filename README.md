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

`make setup` génère `.env` avec une clé secrète aléatoire propre à votre installation. Ce fichier n'est jamais versionné, et seuls `make setup`, `make run`, `make classe`, `make demo` et `make superuser` le lisent. Les vérifications (`make check`, `make verify`, CI) utilisent `.env.test`, versionné et sans valeur : un clone neuf peut tout vérifier sans clé.

### Windows sans make (PowerShell)

```powershell
uv run --no-project python scripts/gen_env.py
uv sync --locked
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py createsuperuser
uv run --env-file .env python manage.py runserver
```

## En classe : `make classe`

```bash
make classe                 # port 8000 ; autre port : make classe PORT=8080
```

Le PC de l'enseignant sert alors l'application aux téléphones de la salle, sur le même réseau Wi-Fi :

- un serveur de production (waitress), jamais en mode debug, même si `.env` contient `DJANGO_DEBUG=1` ;
- les migrations sont appliquées au démarrage ;
- le terminal affiche l'adresse à ouvrir sur les téléphones, par exemple `http://192.168.1.23:8000/`, et celle de l'espace enseignant sur le PC (`http://localhost:8000/prof/`) ;
- le tableau projette l'adresse des téléphones, même s'il est ouvert en `localhost` ;
- l'espace enseignant ne s'ouvre que sur ce PC, par `http://localhost:…/prof/` : les téléphones, et tout autre appareil du réseau, n'y ont pas accès. Sur le PC lui-même, l'adresse du réseau local est aussi refusée pour l'espace enseignant : passer par `localhost`.

Si l'adresse détectée n'est pas la bonne (VPN, plusieurs cartes réseau) : `make classe ADRESSE=192.168.1.23` (une adresse IPv4 ou un nom de machine, sans `http://` ni port).

Sous Windows sans make : `uv run --env-file .env python -m config.classroom` (options `--port` et `--adresse`).

Points à vérifier avant le premier cours :

- **Pare-feu.** Au premier lancement, Windows demande d'autoriser Python : l'autoriser sur les réseaux privés.
- **WSL.** Lancer le mode classe depuis Windows et non depuis WSL : l'adresse d'une machine WSL n'est pas joignable depuis les téléphones (sauf réseau WSL en mode « mirrored »).
- **Wi-Fi d'école.** Certains réseaux isolent les appareils entre eux : les téléphones ne joignent alors pas le PC. Essayer avant le cours depuis un téléphone. Voir SPEC.md, §5.

## Premier cours

### Se faire la main : `make demo`

```bash
make demo
```

La commande crée un compte enseignant `demo`, un groupe « Démo » de six étudiants fictifs et le QCM du fichier [demo/qcm-demo.txt](demo/qcm-demo.txt), au format AMC-TXT. Elle affiche le mot de passe du compte : il change à chaque lancement, et la commande réutilise le groupe et le QCM déjà créés. Si un compte `demo` existe déjà, son mot de passe est remplacé : ne pas donner ce nom à un vrai compte. Ensuite, `make run`, connexion sur `http://localhost:8000/prof/`, et le parcours ci-dessous, avec un téléphone, ou plusieurs onglets du navigateur, pour jouer les étudiants.

Sous Windows sans make : `uv run --env-file .env python manage.py migrate`, puis `uv run --env-file .env python manage.py demo`.

### Le parcours réel

1. **Avant le cours, essayer un vrai fichier.** L'import AMC a été construit sans fichier réel (SPEC.md, §5). Importer au moins un ancien QCM, relire le récapitulatif et comparer quelques notes avec celles d'AMC.
2. **Importer le QCM.** Espace enseignant, « QCM », puis « Importer un fichier AMC » : choisir le fichier `.txt` d'AMC, puis « Analyser ».
   - Une erreur de syntaxe refuse le fichier, avec la ligne et la raison.
   - Sinon, un récapitulatif liste les questions à importer, celles qui sont écartées (question ouverte, formule, image…, avec la ligne et la raison) et les textes ignorés. « Importer » crée le QCM, dans l'ordre du fichier, avec le barème du fichier.
   - Le QCM se relit et se modifie ensuite depuis sa fiche ; les questions sont dans la « Banque de questions ».
3. **Importer le groupe.** « Groupes », puis « Importer un groupe » : un CSV `numéro;nom` par ligne.
4. **Lancer le mode classe.** Sur le PC relié au vidéoprojecteur et à eduroam : `make classe`. Vérifier que l'adresse affichée pour les téléphones est bien celle d'eduroam (de la forme `172.x.x.x`), sinon `make classe ADRESSE=…`. Ouvrir l'espace enseignant par `http://localhost:8000/prof/`, sur ce PC. Voir « En classe » ci-dessus, et le risque principal : un Wi-Fi qui isole les appareils (SPEC.md, §5).
5. **Faire passer.** « Sessions », puis « Lancer une session » : QCM, groupe, nombre de questions affichées à la fois et durée par question, puis « Lancer ».
   - Le tableau projette l'adresse et le QR code ; les étudiants s'identifient par leur numéro, et leur nom apparaît au tableau.
   - « Démarrer » quand tout le monde est là. « +10 s » ajoute du temps à la question en cours.
6. **Exporter les résultats.** À la fin, « Résultats » : les notes, jamais projetées, puis « Télécharger le CSV ».

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
config/     réglages (lus depuis l'environnement), routes, vues transverses, mode classe (classroom.py)
bank/       banque de questions, QCM, barème AMC (scoring.py : calcul pur),
            import AMC-TXT (amc_txt.py : analyse pure ; importer.py), commande demo
roster/     groupes d'étudiants, import CSV
live/       sessions en direct : QR code de jonction, déroulement, réponses, résultats
templates/  gabarits HTML          static/  CSS et JS, sans script ni style inline
tests/      unit/ · integration/ · e2e/ (Playwright) · spec_trace.py (traçabilité SPEC.md)
            factories.py (données de test fictives, créées via les formulaires)
scripts/    gen_env.py (création du .env local)
demo/       qcm-demo.txt (fichier AMC-TXT fictif de démonstration)
.claude/    environnement de l'agent : réglages, hooks, procédure d'incrément, auditeur de spec
```
