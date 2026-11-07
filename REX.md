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

### Questions posées au commanditaire
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

---

## I2 — Groupes d'étudiants (import CSV)

### Objectif
- L'enseignant importe un groupe nommé à partir d'un fichier CSV (numéro, nom), le consulte et le supprime.
- Un fichier invalide est refusé en entier, avec un message qui désigne les lignes fautives.

### Questions posées au commanditaire
- **Que faire d'un groupe après l'import ?** Réponse : importer, consulter, supprimer. Pour corriger une liste, on supprime le groupe puis on le réimporte (GRP-03).
- **Format du numéro.** Réponse : chiffres uniquement, pour que le téléphone affiche le pavé numérique en I3.
- **Format du CSV, choisi par moi** et décrit dans SPEC §2 bis, car c'est un détail technique :
  - séparateur `;` ou `,` ;
  - en-tête facultatif ;
  - encodage UTF-8 ou Windows-1252, les deux sorties possibles d'Excel en français.

### Problèmes rencontrés
- **Faux pas sur les commits.**
  - Les tests rouges importent un module `roster` qui n'existe pas encore. ruff le classe alors parmi les bibliothèques externes ; une fois le module créé, le classement change.
  - Correctif : créer le paquet vide dès le commit des tests rouges.
  - J'ai aussi dû corriger deux fois un message de commit local qui décrivait mal son contenu. Règle : relire `git show --stat` avant d'amender.
- **Ce que la revue de code a trouvé dans la lecture du CSV.** Six cas que mes tests ne couvraient pas, chacun reproduit par la revue :
  - une cellule de plus de 128 Ko fait planter le module `csv` (erreur 500) ;
  - `\d` accepte aussi les chiffres pleine chasse et arabes ;
  - un fichier UTF-16 (« Texte Unicode » d'Excel) produisait des erreurs absurdes au lieu du message d'encodage ;
  - `splitlines()` coupe aussi sur des caractères rares (saut de page, U+2028), ce qui faussait les numéros de ligne ;
  - les noms acceptaient des caractères de contrôle ;
  - un double clic sur « Importer » pouvait provoquer une erreur 500.

  Tous sont corrigés et couverts par un test.
- **Une heuristique d'en-tête qui peut ignorer une vraie ligne.** Une première ligne « abc;DUPONT » est prise pour un en-tête. Je garde la règle, plus sûre que l'alternative : celle-ci aurait ignoré en silence une faute de frappe comme « 12a;DUPONT ». En revanche, je la rends visible : le message de confirmation cite la ligne ignorée.
- **L'auditeur de spec : 30 contre-épreuves, 4 survivantes.**
  - Une ligne vide avant une ligne fautive faussait le numéro annoncé, sans qu'aucun test ne le voie.
  - Une suppression « douce » qui garde le nom pris passait aussi. Elle aurait empêché de réimporter un groupe corrigé.
  - Les limites tout juste acceptées n'étaient pas testées (20 chiffres, 200 caractères).

  J'ai ajouté les tests et rejoué ces contre-épreuves : toutes sont maintenant détectées.

### Ce qui a bien marché
- **Isoler la lecture du CSV dans une fonction pure** (des octets en entrée, des étudiants ou des erreurs en sortie). Elle se teste vite et à fond (30 cas), et le formulaire Django ne fait que la brancher.
- **Le parcours E2E envoie de vrais fichiers par le champ d'envoi du navigateur**, avec plusieurs variantes : Windows-1252 avec en-tête et ligne vide, UTF-8 avec BOM et virgule.
- **La règle de CLAUDE.md « cas refusé et cas tout juste accepté », ajoutée en I1.** Je ne l'avais pas appliquée partout, et l'auditeur l'a vu tout de suite.

### Ce que j'aurais dû savoir dès le départ
- **Un fichier venu de l'extérieur, c'est une liste de pièges connus** : encodages, BOM, UTF-16, séparateurs, guillemets multilignes, lignes vides, colonnes vides finales, chiffres non ASCII, caractères de contrôle, taille, limite de champ du module `csv`. Il faut les tester dès le premier jet.
- **Les numéros de ligne annoncés doivent être ceux du fichier.** Le lecteur `csv` lit directement le texte (`newline=""`), sans découpage préalable.
- **Lire un fichier envoyé avec une borne** (`read(MAX + 1)`) : sans borne, on charge en mémoire un fichier qu'on va refuser.

### Choix techniques et leur raison
- **Aucune nouvelle dépendance.** Le module `csv` de Python suffit.
- **Le fichier envoyé n'est jamais écrit sur le disque** ; seul son contenu, lu et validé, est enregistré. Les vraies listes d'étudiants ne vont pas dans le dépôt (`.gitignore`), et les tests n'utilisent que des noms fictifs.
- **Les limites de longueur sont définies dans le module de lecture**, et les modèles les reprennent : une seule source.
- **`TeacherForm` et `table_field` sont déplacés dans `config/forms.py`,** pour que `roster` ne dépende pas de `bank`.
- **Contraintes pour la suite, inscrites dans CLAUDE.md :**
  - un participant de session garde son propre exemplaire du numéro et du nom, pour que supprimer un groupe n'efface aucun résultat ;
  - l'export CSV des résultats (I6) devra neutraliser les cellules qui commencent par `=`, `+`, `-` ou `@`, contre l'injection de formules.

---

## I3 — Lancement de session et accueil des étudiants

### Objectif
- L'enseignant lance une session (QCM, groupe, N, t) et obtient un code à 6 chiffres.
- Le tableau projeté affiche l'adresse, le code et les noms des étudiants connectés, en direct. L'enseignant démarre la session.
- Sur son téléphone, l'étudiant saisit le code puis son numéro et voit son nom. Son identité survit à un rechargement.

### Questions posées au commanditaire
- **Recours quand un numéro est déjà pris** (téléphone en panne).
  - Ma première question, trop abstraite, a reçu une réponse à côté : « le numéro est fixe toute l'année ».
  - Reformulée sur un scénario concret (Alice, batterie vide, emprunte le téléphone d'un voisin), elle a reçu une réponse claire : aucun recours dans l'application, l'enseignant a des copies papier d'AMC.
  - Leçon : une question fonctionnelle se pose sur un scénario, pas sur une règle.
- **Ce que projette la liste des connectés.** Les noms seulement, pas les numéros.
- **Quand le contenu est figé.** Au lancement et non au démarrage. Cela modifie l'hypothèse H8, que le commanditaire avait validée : c'est dit explicitement dans SPEC.md.
- **Confirmation sur le téléphone.** Le nom de l'étudiant.

### Problèmes rencontrés
- **La CI, lente une deuxième fois** (11 min pour 7 s de tests).
  - Le journal l'a montré : le téléchargement des paquets système de Chromium depuis un miroir apt allait à 32 ko/s.
  - Correctif : installer seulement le navigateur sans interface, sans dépendances système (le runner ubuntu-24.04 les a déjà), avec un cache. Le job `tests` passe à 47 s.
  - Vérifié tôt, grâce à une PR ouverte en brouillon dès le début de l'incrément.
- **ruff et les tests rouges.**
  - En I2, j'avais retiré la liste `known-first-party` de la configuration de ruff, qu'une revue jugeait inutile. Or les versions récentes de ruff classent un import parmi ceux du projet seulement si le module existe. Les tests rouges, qui importent `live.forms` avant qu'il soit écrit, étaient donc mal triés.
  - La liste est rétablie, avec un commentaire qui explique pourquoi. Leçon : une recommandation de revue se vérifie dans le cas qui avait motivé la configuration.
- **Ce que la revue de code a trouvé.**
  - Une boucle de tirage du code qui pouvait ne jamais finir.
  - Une copie figée faite hors transaction : un QCM vidé au dernier moment donnait une session sans question.
  - L'attribut HTML `maxlength` coupait un code tapé avec des espaces.
  - Un paramètre étranger dans l'adresse d'accueil affichait une erreur.
  - Un double clic sur « Démarrer » déplaçait l'heure de départ.

  Tout est corrigé et testé.
- **Ce que l'auditeur de spec a trouvé.** 31 contre-épreuves, 4 survivantes :
  - une identité d'appareil qui aurait débordé d'une session à l'autre ;
  - un code sans ses zéros de tête, détecté seulement une fois sur dix ;
  - un rafraîchissement ralenti à 4 s, que les tests acceptaient ;
  - des noms insérés comme du HTML.

  J'ai ajouté les tests (le « direct » est chiffré à 2 s dans SPEC) et rejoué les quatre contre-épreuves : toutes détectées.

### Ce qui a bien marché
- **Un appareil = un contexte de navigateur** (`new_phone()`). Tester à plusieurs téléphones est naturel : cookies séparés, comme dans une vraie classe.
- **La copie figée en JSON typé (`TypedDict`)** : aucune clé étrangère vers la banque ni vers les groupes. Le test de SES-03 supprime tout après le lancement, et la session continue.
- **La contrainte d'unicité en base comme seul arbitre du « numéro déjà pris »** : la course entre deux téléphones est réglée sans verrou applicatif.

### Ce que j'aurais dû savoir dès le départ
- **Un aléa se teste en le forçant** (monkeypatch du générateur), sinon le test passe neuf fois sur dix. Même chose pour une collision de codes.
- **Une valeur « en direct » doit être chiffrée.** Sinon, le délai d'attente des tests (5 s) devient la spécification par défaut.
- **`maxlength` et le nettoyage côté serveur ne font pas bon ménage** : le navigateur coupe avant que le serveur ne normalise.
- **Une recommandation de revue sur la configuration se revérifie dans le cas qui l'avait motivée.**

### Choix techniques et leur raison
- **Code de session à 6 chiffres**, tiré avec `secrets` : il se tape sur le pavé numérique, comme le numéro d'étudiant. 20 tentatives au plus en cas de collision.
- **Identité dans la session Django** (base de données côté serveur, simple clé dans le cookie). Le client ne peut pas la forger.
- **Polling JSON chaque seconde** par un script externe (CSP stricte), qui insère du texte et jamais du HTML. Il s'arrête une fois la session démarrée.
- **Aucune nouvelle dépendance.**
- **Point d'attention transmis au commanditaire.** Quelqu'un qui connaît le code peut, par un script, essayer tous les numéros du groupe et les réserver avant les vrais étudiants. Ceux-ci n'ont alors aucun recours dans l'application. La parade actuelle, déjà prévue par la spec, est que le tableau affiche les connectés avant le départ. Une vraie protection demanderait un secret par étudiant, ce qui est une décision fonctionnelle.

---

## I4 — Déroulement d'une session

### Objectif
- **Le cœur de l'application.** Au tableau, les questions défilent par groupes de N, chacune sur sa couleur et avec son numéro. Les créneaux de t secondes passent seuls.
- **Sur le téléphone**, l'étudiant voit la couleur de sa question et les propositions mélangées pour lui, jamais l'énoncé. Il répond, peut changer d'avis jusqu'à l'échéance, et sa réponse est refusée ensuite.
- **La rotation** fait répondre chacun à toutes les questions, dans des ordres différents.
- **Ajouté à la demande du commanditaire :** avant le démarrage, l'enseignant peut libérer un numéro usurpé (SES-04).

### Questions et décisions
- **Validées par le commanditaire :**
  - le délai de 2 s pour le « direct » ;
  - le recours contre l'usurpation : libération d'un numéro avant le démarrage, depuis une page non projetée qui montre les numéros. Je l'ai placé en I4 parce qu'il touche au démarrage.
- **Décisions dérivées, écrites dans SPEC.md :**
  - réponse enregistrée à chaque choix, sans bouton « Valider » ;
  - propositions sans lettres sur le téléphone ;
  - écran « Session terminée » au tableau et sur les téléphones.
- **Question ouverte, posée au commanditaire :** sur une question simple (boutons radio), l'étudiant ne peut pas revenir à « pas de réponse ». C'est important, car AMC peut noter différemment une non-réponse (v) et une mauvaise réponse (m).

### Problèmes rencontrés
- **Concevoir le temps sans tâche de fond.** Le créneau en cours se calcule à partir de l'heure de démarrage, par un module pur. Chaque page et chaque état JSON le recalculent, et une page se recharge dès que son « jeton » (phase, groupe ou créneau) change.
  - Avantage : simple, robuste à la veille des téléphones.
  - Limite repérée pour I5 : « +10 s » ne pourra pas se faire en décalant l'heure de départ, car le créneau en cours reculerait. Le module devra connaître les secondes ajoutées par créneau. C'est consigné dans CLAUDE.md.
- **Tester le temps.**
  - Un seul test tourne en temps réel (deux créneaux de 5 s) : il prouve le passage automatique.
  - Les autres « avancent l'horloge » en reculant l'heure de démarrage en base.
  - Pour une échéance à la demi-seconde près, il fallait placer le déroulement à un instant précis, quel que soit le temps déjà écoulé dans le test (`jump_to`).
- **Ce que la revue de code a trouvé** (aucune revue précédente ne l'avait vu) :
  - deux choix rapides sur un réseau lent pouvaient arriver dans le désordre et enregistrer l'ancien. Corrigé : file d'envoi sur le téléphone, testée en retenant volontairement la première requête ;
  - un double insert donnait une erreur 500 ;
  - deux arrivées simultanées, ou une libération, pouvaient donner le même rang à deux étudiants et casser la rotation. Corrigé : rangs uniques en base, nouvel essai en cas de conflit, renumérotation au démarrage ;
  - une libération pouvait passer en même temps que « Démarrer ». Corrigé : suppression conditionnelle et atomique ;
  - chaque interrogation, chaque seconde, décodait la copie figée entière. Corrigé : nombre de questions stocké à part.
- **Ce que l'auditeur de spec a trouvé.** 35 contre-épreuves, 5 survivantes :
  - un compte à rebours figé à 0 au second créneau ;
  - un temps faux sur les téléphones ;
  - la bonne réponse mise en gras au tableau, ou un compteur de répondants : une liste noire de mots ne les voyait pas ;
  - un refus 10 s avant l'échéance.

  J'ai ajouté les tests (liste blanche du contenu du tableau, temps comparé entre écrans, cas « tout juste avant l'échéance ») et rejoué les 5 : toutes détectées.
- **Contre-audit.** Une bonne réponse signalée par une simple classe CSS (contenu ajouté par `::after`, bordure) passait encore. Le test vérifie désormais que les propositions n'ont aucun attribut, aucun pseudo-élément, et toutes les mêmes propriétés de style calculées.

- **Un test intermittent, révélé par hasard.** Pendant le contre-audit, le test de rotation a échoué une fois sous une mutation qui ne le concernait pas. Relancé 8 fois de suite, il échouait une fois sur 8.
  - Cause : la base de test SQLite en mémoire partagée refuse aussitôt un accès concurrent (« table is locked ») au lieu d'attendre. Le test, qui avance l'horloge en base, entrait parfois en concurrence avec les téléphones, qui interrogent le serveur chaque seconde.
  - Correction à la racine : base de test dans un fichier. Résultat : 0 échec sur 25 lancements, et la suite E2E 3 fois de suite sans échec.

### Ce qui a bien marché
- **Le module pur du déroulement**, avec ses 58 tests unitaires (rotation vérifiée pour N de 1 à 6 et jusqu'à 7 questions). La logique difficile est prouvée hors navigateur.
- **Un jeton de page** et un seul mécanisme de suivi du direct (`qcm.follow`), partagé par le tableau et le téléphone.
- **Les interceptions réseau de Playwright** pour reproduire un téléphone qui perd le réseau, ou un réseau très lent.
- **Forcer le mélange des propositions dans le serveur de test** (même processus) rend déterministe la vérification « le téléphone envoie l'indice canonique et pas la position à l'écran ».

### Ce que j'aurais dû savoir dès le départ
- **Une liste noire ne prouve pas une absence.** Pour « le tableau n'affiche rien d'autre », il faut une liste blanche du texte visible et une comparaison des styles.
- **Toute action déclenchée par l'utilisateur peut arriver en double ou dans le désordre** : double clic, deux onglets, réseau lent. Prévoir dès le premier jet des mises à jour conditionnelles, des contraintes d'unicité et une file d'envoi.
- **Un test qui dépend d'un tirage aléatoire** ne détecte une erreur qu'une fois sur n. Il faut forcer le tirage.
- **Chiffrer chaque délai visible** et le vérifier sur tous les écrans, pas seulement sur le premier.
- **Un échec « isolé » est un signal.** Relancer le test plusieurs fois de suite avant de fusionner : un test intermittent en CI ruine la confiance dans toute la vérification.

### Choix techniques et leur raison
- **Aucune nouvelle dépendance.** Polling chaque seconde, avec des rechargements étalés au hasard sur 300 ms pour ne pas recevoir la classe entière dans la même milliseconde.
- **Réponses stockées en indices canoniques** (A = 0) de la copie figée. Le reçu du QR code (lettres du tableau) et la notation AMC (I6) les liront directement.
- **Six couleurs claires, numérotées**, avec un texte sombre lisible. Le numéro est le repère pour les étudiants daltoniens.

---

## I5 — Temps additionnel et effacement d'une réponse

### Objectif
- **+10 s (TPS-01).** Pendant un créneau, l'enseignant ajoute 10 secondes depuis le tableau. Le temps restant augmente partout, les créneaux suivants sont décalés d'autant, et les ajouts se cumulent.
- **« Effacer ma réponse » (ETU-09).** Réponse du commanditaire à la question ouverte en I4 : sur une question simple, l'étudiant peut revenir à « pas de réponse ». C'est important pour la notation AMC, qui distingue une non-réponse (v) d'une mauvaise réponse (m).

### Questions et décisions
- **Réponse du commanditaire :** oui à « Effacer ma réponse » sur les questions simples. C'est la nouvelle exigence ETU-09, livrée dans cet incrément. Sur une question multiple, décocher toutes les cases suffisait déjà.
- **Décisions dérivées, écrites dans SPEC.md :**
  - le bouton « +10 s » est sur le tableau, pendant le déroulement seulement ;
  - un clic qui arrive après la fin du créneau n'ajoute rien : le temps n'est jamais ajouté à un créneau que l'enseignant n'a pas vu ;
  - le téléphone confirme l'effacement par « Réponse effacée ».
- **Correction de forme :** le commanditaire est désormais désigné au masculin dans tous les documents.

### Problèmes rencontrés
- **Ne pas faire reculer le temps.** Décaler l'heure de démarrage aurait fait revenir le déroulement en arrière, comme prévu dès I4. Le module pur reçoit désormais les secondes ajoutées à chaque créneau et calcule des échéances cumulées. L'heure de démarrage ne bouge jamais.
- **Deux clics simultanés.** Un compteur lu puis réécrit en perd un. Chaque clic est donc une ligne en base : deux clics s'ajoutent toujours.
- **Un clic au tout dernier moment.** Entre la vérification « le créneau est en cours » et l'écriture, le créneau peut se terminer, et l'ajout le rouvrirait : les téléphones repasseraient au créneau précédent. L'échéance est revérifiée juste avant de valider l'écriture, et l'ajout est annulé si elle est passée.
- **Le tableau ne se recharge qu'au changement de groupe.** Avec N = 2, il reste sur la même page pendant deux créneaux. Le bouton doit pourtant viser le créneau en cours : l'état interrogé chaque seconde le donne, et le script du tableau le reporte dans le formulaire.
- **Un test trop rapide.** Mon premier test cliquait sur « +10 s » aussitôt après avoir avancé l'horloge, avant que le tableau ne l'ait vu : le clic visait l'ancien créneau et était refusé, comme prévu. Le test attend désormais que le tableau affiche le nouveau créneau, comme l'enseignant le verrait.

### Ce qui a bien marché
- **La limite repérée dès I4 et consignée dans CLAUDE.md** a donné la bonne conception d'emblée : aucun détour par un décalage de l'heure de démarrage.
- **Le module pur** : le temps ajouté se teste en quelques lignes (échéances, décalage des suivants, rotation inchangée), sans navigateur.
- **Les aides de test du déroulement mises en commun** (`tests/e2e/live_setup.py`) : les tests I5 réutilisent les mêmes questions reconnaissables et les mêmes préconditions qu'en I4.

### Ce que j'aurais dû savoir dès le départ
- **Une action de l'enseignant vise ce qu'il voit.** Elle doit transporter ce qu'elle vise (ici le créneau), sinon le serveur l'applique à ce qui est en cours à son arrivée, ce qui peut être autre chose.
- **Un test doit attendre ce que l'utilisateur attendrait.** Avancer l'horloge en base ne met pas l'écran à jour instantanément.

### Choix techniques et leur raison
- **Aucune nouvelle dépendance.**
- **Une ligne par ajout de temps**, plutôt qu'un compteur ou une liste en JSON : l'insertion est atomique sans verrou, et l'historique des ajouts est conservé.
- **Bouton « +10 s » sans script dédié** : un simple formulaire qui recharge le tableau, lequel recalcule le temps restant. Les téléphones le reçoivent à leur interrogation suivante, en 1 s au plus.
