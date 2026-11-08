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
  - refus de `--no-verify`, du push forcé, du commit et du push sur main, de la lecture de `.env` (*corrigé en R : ce dernier refus évite les accidents, il n'empêche pas de lire le fichier*) ;
  - `make check` obligatoire avant de rendre la main ;
  - un état du projet affiché au démarrage, déduit de git.
- **Hors session.**
  - CI GitHub en deux checks requis : `quality` (gitleaks sur tout l'historique, ruff, pyright, checks Django) et `tests` (tous les tests, spec, couverture ≥ 90 %).
  - `main` protégée avec `enforce_admins`.
  - Fusions par merge commit uniquement, pour qu'une ligne de `--first-parent` corresponde à un incrément.
- **Secrets.**
  - La clé Django n'existe que dans `.env`, généré localement ; en CI, une clé éphémère est générée à chaque run. *(Remplacé en R : les vérifications et la CI utilisent `.env.test`, versionné et sans secret.)*
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
- **Sandbox de Claude Code.** *Oublié dans cet inventaire : il n'y était ni retenu ni écarté. Évalué et écarté en R, voir cette section.*

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
- **Tests d'acceptation d'abord : règle non respectée en I0.** *(Corrigé en R ; ce paragraphe affirmait que « l'historique prouve » cette discipline.)* Dans cet incrément, le code et les tests ont été écrits ensemble. Pour produire un commit rouge, j'ai vidé temporairement `config/urls.py`, constaté les 6 échecs, puis rétabli le fichier ; les 8 commits ont été créés en 51 secondes. Les échecs étaient réels, mais ils ne montrent pas que les tests ont précédé le code. Un historique git prouve l'ordre des commits, jamais l'ordre d'écriture.

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
- **Ce que la revue de code a trouvé :**
  - deux clics à quelques centièmes de seconde de l'échéance : le second se comparait à l'échéance lue avant que le premier ne soit validé, et était annulé à tort. Corrigé : le clic est d'abord écrit, ce qui prend le verrou d'écriture, puis le créneau en cours est recalculé avec les ajouts déjà validés. Un test reproduit l'entrelacement en injectant l'horloge ;
  - « Effacer ma réponse » confirmait un effacement même quand rien n'était choisi. Le bouton est désormais inactif dans ce cas.
- **Ce que l'auditeur de spec a trouvé.** 23 contre-épreuves, aucune survivante à l'ensemble de la suite. Trois ne tombaient qu'en intégration : supprimer le contrôle du créneau visé, la revérification finale, ou y compter son propre clic. J'ai ajouté un test de bout en bout du clic tardif, où le tableau ne voit pas la fin du créneau. Il attrape la première, et je l'ai rejouée. Les deux autres portent sur quelques millisecondes : seul le test d'intégration à horloge injectée peut les reproduire.
  - Il a aussi relevé deux précisions dérivées absentes de SPEC.md (« Réponse effacée », bouton inactif sans réponse), désormais reportées dans ETU-09.
  - Son premier lancement a échoué (« no such table ») parce qu'une autre exécution de pytest utilisait la même base de test en fichier. C'est consigné dans CLAUDE.md.
- **Limite connue.** Entre ce dernier calcul et la validation, il reste une fenêtre de quelques millisecondes. Un clic validé juste après l'échéance pourrait faire revenir un téléphone, pendant moins d'une seconde, au créneau précédent. La fermer demanderait de comparer l'heure dans la base elle-même, ce qui est disproportionné ici.
- **Le tableau ne se recharge qu'au changement de groupe.** Avec N = 2, il reste sur la même page pendant deux créneaux. Le bouton doit pourtant viser le créneau en cours : l'état interrogé chaque seconde le donne, et le script du tableau le reporte dans le formulaire.
- **Un test trop rapide.** Mon premier test cliquait sur « +10 s » aussitôt après avoir avancé l'horloge, avant que le tableau ne l'ait vu : le clic visait l'ancien créneau et était refusé, comme prévu. Le test attend désormais que le tableau affiche le nouveau créneau, comme l'enseignant le verrait.
- **Un commit parti avec un test en échec.** *(Ajouté en R, omis à l'époque.)* J'enchaînais les tests, un filtre `tail` et le commit. `tail` réussissant toujours, le commit `8dfdcda` est parti malgré « 1 failed ». Le résultat, relu aussitôt, a montré un test intermittent (1 échec sur 3), corrigé par le commit suivant de ce test. La CI ne l'aurait attrapé qu'au hasard. Voir la section R pour la règle et le garde-fou.

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

---

## I6 — Fin de session : QR code, résultats et export CSV

### Objectif
- **QR code (FIN-01).** À la fin, chaque téléphone identifié affiche un QR code de ses réponses : code de session, numéro, puis une ligne par question, dans l'ordre où l'étudiant l'a eue.
- **Résultats (RES-01).** L'enseignant voit les notes calculées selon le barème AMC figé au lancement.
- **Export (RES-02).** Il télécharge un CSV avec, pour chaque question, la réponse donnée et les points obtenus.

### Questions et décisions
- **Quatre questions posées au commanditaire avant le code, toutes tranchées selon ma recommandation :**
  - la référence d'une question est son rang dans le QCM (Q1 à Qn). L'identifiant de banque prévu en I3 n'apparaissait nulle part dans l'interface ;
  - les notes sont sur une page non projetée, disponible seulement une fois la session terminée ;
  - les étudiants jamais connectés sont listés « Absent », sans note ;
  - le CSV suit le format d'Excel en français : point-virgule, virgule décimale, UTF-8 avec BOM.
- **Décisions dérivées, écrites dans SPEC.md :**
  - le QR code est du texte brut, lisible par n'importe quelle application ;
  - les créneaux manqués par un retardataire figurent dans le QR code, sans réponse ;
  - dans le CSV, `-` signifie pas de réponse, et les cellules d'un absent sont vides ;
  - la liste des sessions indique l'état de chacune ;
  - au-delà de la capacité d'un QR code, un message remplace le QR code. Ce point est à confirmer.

### Problèmes rencontrés
- **Prouver ce que contient un QR code.** Une donnée cachée dans la page aurait permis un test facile, mais elle ne prouve pas que l'image est lisible. Le test fait une capture de l'image sur le téléphone émulé et la décode, comme le ferait un lecteur. Le texte est encodé en UTF-8 (« Étudiant »), et le décodage le confirme.
- **Une lettre juste par hasard.** Avec un mélange aléatoire, une lettre calculée sur la position à l'écran plutôt que sur l'ordre du tableau tombe juste une fois sur six. Les tests forcent l'ordre inverse sur les téléphones, comme en I4.
- **Un barème qui distingue chaque cas.** Avec le barème par défaut (b=1, m=0, v=0), une non-réponse et une mauvaise réponse valent pareil. Les tests utilisent donc un v non nul, un m négatif et un plancher, et chaque note attendue est calculée à la main dans un commentaire.
- **Un test intermittent introduit par moi.** Le test « pas de QR code avant la fin » plaçait le déroulement à 1 s de l'échéance. Le téléphone, qui interroge l'état chaque seconde, sautait parfois le dernier créneau et passait directement à la fin : 3 échecs sur 5. Je l'ai repéré en relançant après `/simplify`. Le test laisse désormais 10 s de marge, puis avance à la fin. Résultat : 8 réussites sur 8, et le fichier entier 3 fois de suite sans échec. C'est consigné dans CLAUDE.md.
- **Ce que les revues ont trouvé :**
  - `/simplify` : la note affichée (« Absent » ou nombre) était décidée à trois endroits, et le barème relu à chaque question. J'ai aussi supprimé une requête par session dans la liste des sessions, en préchargeant les ajouts de temps ;
  - `/code-review` : ce préchargement alourdissait les états interrogés chaque seconde et pouvait servir un cache périmé après un « +10 s ». J'ai annulé ce changement : une petite requête par session sur une page de l'enseignant coûte moins qu'un risque sur le chemin chaud. La revue a aussi relevé qu'un QCM d'environ 300 questions dépasse la capacité d'un QR code et provoquait une erreur 500. Un message la remplace désormais ;
  - `/security-review` : aucune vulnérabilité. Notes protégées par la connexion et jamais projetées, QR code toujours celui de l'appareil identifié, CSV neutralisé.
- **Je me suis arrêté après `/security-review`.** *(Ajouté en R, omis à l'époque.)* Le rapport du skill a l'allure d'un compte rendu complet, et je l'ai rendu comme message final : ni audit, ni REX, ni PR, ni fusion. `make check` étant vert, le hook Stop n'a rien signalé. Le commanditaire a dû me relancer 33 minutes plus tard (« Tu t'es arrêté après la revue de sécurité »). Voir la section R pour le garde-fou.
- **Un `exit 0` trompeur sur 16 erreurs pyright.** *(Ajouté en R, omis à l'époque.)* `make verify` tournait en arrière-plan, suivi d'un `;` et d'un `echo` qui écrivait son code dans le journal. L'`echo` réussissant, la commande entière a été annoncée en réussite, alors que le journal disait « exit 2 ». Je l'ai vu en relisant le journal dans la minute, et rien n'a été commité. Voir la section R.
- **Ce que l'auditeur de spec a trouvé.** 31 contre-épreuves, dont 5 survivantes :
  - l'ordre du fichier n'était pas prouvé, car l'ordre d'arrivée des téléphones était le même et l'absent était en dernier ;
  - un étudiant connecté sans aucune réponse pouvait être marqué « Absent » ;
  - avant la fin, des notes affichées en liste plutôt qu'en tableau passaient inaperçues ;
  - un plancher appliqué à tort à v passait, parce que v était positif ;
  - un total négatif neutralisé à tort dans le CSV passait, faute de total négatif.

  Une seule modification des préconditions détecte les cinq : un fichier dans un autre ordre que l'arrivée, avec l'absent au milieu, un étudiant connecté qui ne répond jamais, et des v négatifs. Le test « avant la fin » fait aussi répondre un téléphone et vérifie qu'aucun nom n'apparaît. J'ai rejoué les 5 contre-épreuves : toutes détectées.
  - Il a aussi soulevé une vraie question : Excel retire les zéros de tête d'un numéro à l'ouverture du CSV. Réponse du commanditaire : garder le numéro tel quel, la colonne se reformate en texte au besoin.
- **Limite connue.** Le texte du QR code est encodé en UTF-8 sans marqueur ECI. zxing le lit correctement, mais un lecteur qui supposerait Latin-1 afficherait mal le « É » de « Étudiant ». Les chiffres et les lettres, qui portent l'information, restent justes.

### Ce qui a bien marché
- **Les modules purs** (`receipt.py`, `results.py`) se testent sans navigateur, avec les cas limites : nombres à la française, neutralisation, absent, plancher.
- **La copie figée prévue dès I3.** Les résultats se calculent sans la banque ni le groupe. Le test le prouve en changeant le barème et en supprimant le groupe après le lancement.
- **Les réponses en indices canoniques (I4)** donnent directement les lettres du tableau.

### Ce que j'aurais dû savoir dès le départ
- **Une référence doit être visible là où on la lit.** L'identifiant de banque, figé dès I3 « pour le QR code », n'aurait servi à rien à l'enseignant. Il fallait poser la question plus tôt.
- **Une optimisation sur une page rare peut coûter sur le chemin chaud.** Avant de précharger une relation, regarder qui d'autre lit le même code.
- **Un test de temps doit laisser au téléphone le temps d'observer.** Une marge plus courte que la période d'interrogation rend le test aléatoire.
- **Des préconditions trop régulières cachent des fautes.** Ordre d'arrivée identique à l'ordre du fichier, v positif, aucun total négatif : chaque coïncidence laisse passer une erreur. Choisir des données de test où chaque règle donne un résultat qu'aucune autre règle ne donnerait.

### Choix techniques et leur raison
- **segno**, prévu dès I0 : en pur Python, sans dépendance, il produit un SVG. Le SVG est servi en URI `data:` dans une balise `<img>`, ce que la CSP autorise déjà (`img-src data:`), et il ne peut exécuter aucun script.
- **zxing-cpp et Pillow, en dépendances de test seulement** : décoder le QR code depuis une capture d'écran. Ce sont des paquets précompilés, sans bibliothèque système à installer, contrairement à pyzbar ; OpenCV aurait été beaucoup plus lourd.
- **Pas de nouveau modèle.** Les résultats se recalculent à la demande, à partir de la copie figée et des réponses : rien à garder synchronisé.
- **CSV écrit par le module standard `csv`**, qui gère les guillemets. Seuls les champs de texte venus de l'extérieur (numéro, nom) sont neutralisés, pas les nombres calculés.

---

## I7 — Mode classe : serveur de production local

### Objectif
- **CLA-01.** Lancer l'application en classe sur le PC de l'enseignant, avec un serveur de production local, sans mode debug.
- La faire fonctionner de bout en bout depuis les téléphones du réseau local, et afficher l'adresse à ouvrir.
- Prouver tout cela par des tests de bout en bout contre ce serveur, et non contre le serveur de test de Django.

### Questions et décisions
- **Aucune question fonctionnelle bloquante.** CLA-01 est précise, et les choix restants sont techniques. Ils sont écrits dans SPEC.md comme *dérivés*, pour validation :
  - une commande, `make classe` ;
  - l'adresse du réseau local, affichée dans le terminal et projetée au tableau ;
  - une adresse imposable à la main ;
  - la tenue de charge d'une classe entière ;
  - des pages d'erreur en français.
- **Le plan n'est pas passé par le plan mode.** L'incrément a été mené d'un seul tenant, sur un objectif donné par le commanditaire. Le plan est donc détaillé dans la PR.
- **L'adresse projetée.** Le tableau affichait l'adresse par laquelle il avait été ouvert. Or l'enseignant ouvre naturellement `localhost` sur son PC, et le tableau aurait alors projeté une adresse injoignable depuis les téléphones. Le mode classe impose donc l'adresse du réseau local, détectée au lancement.

### Problèmes rencontrés
- **SQLite refusait les écritures simultanées.** Le test de charge (40 téléphones qui valident leur numéro au même instant) a échoué dès son premier lancement : erreurs 500, « database is locked ».
  - Une transaction ordinaire commence par lire, puis demande le verrou d'écriture. Si une autre transaction écrit déjà, SQLite refuse aussitôt, sans attendre, pour éviter un interblocage.
  - Les tests précédents, avec trois ou quatre téléphones, ne pouvaient pas le voir.
  - Correctif : les transactions demandent le verrou d'écriture dès leur début (mode `IMMEDIATE`), et les suivantes attendent leur tour, jusqu'à 20 s. Le même test passe ensuite 3 fois sur 3.
- **Hors mode debug, une erreur 500 ne laisse aucune trace.** Django n'affiche alors rien dans le terminal. Pour trouver la cause, j'ai ajouté une journalisation des erreurs des requêtes sur la console. Elle reste : en classe, c'est le seul moyen de comprendre un incident.
- **Les alertes de file d'attente de waitress** (« Task queue depth ») s'affichaient dès que toute la classe envoyait au même instant. Elles sont normales mais alarmantes pour l'enseignant, et sont donc masquées. Le nombre de fils passe de 4 à 16.
- **Les pages d'erreur étaient en anglais.** Hors mode debug, Django affiche ses pages par défaut (« Not Found »). Les pages 400, 403 (formulaire expiré), 404 et 500 sont désormais en français, comme le reste de l'interface.
- **Le serveur du mode classe ne reconnaissait pas le mot de passe de test.** Les tests hachent les mots de passe en MD5 pour aller vite, et un vrai serveur ne connaît pas ce hachage. Le test du mode classe crée donc le compte enseignant avec les hachages de production.
- **Une vérification gâchée par mon propre hook.** J'ai lancé `make verify` en arrière-plan, puis rendu la main. Le hook Stop a alors lancé `make check`, un second pytest sur la même base de test : 8 tests en erreur (« no such table », « attempt to write a readonly database »), sans rapport avec le code. Relancée au premier plan, la vérification est verte. Règle ajoutée à CLAUDE.md.
- **Ce que les revues ont trouvé :**
  - `/simplify` (quatre angles) :
    - l'hôte autorisé était recopié à deux endroits : les réglages ajoutent désormais eux-mêmes l'hôte de l'adresse projetée ;
    - le port par défaut était défini deux fois ;
    - une vérification « refuser le mode debug » ne pouvait jamais se déclencher ;
    - la journalisation coupait aussi les avertissements en développement : elle n'agit plus qu'hors debug ;
    - le test de charge gérait ses fils à la main : il passe par un pool de fils.
  - `/simplify`, constats écartés :
    - **Les reprises après conflit**, rendues inutiles avec SQLite par le mode `IMMEDIATE` : elles restent. Elles protègent toujours si la base change (hébergement en I8), et leurs tests en dépendent.
    - **Des connexions persistantes à la base** : gain modeste, aucun symptôme mesuré.
  - `/code-review`, retenus :
    - **L'espace enseignant ouvert à tout le Wi-Fi de l'école.** Le serveur écoute sur toutes les interfaces, donc un étudiant pouvait ouvrir la page de connexion de l'enseignant, essayer des mots de passe, ou lire une connexion faite en clair depuis un autre appareil. En mode classe, l'espace enseignant ne répond plus qu'au PC lui-même. La contre-épreuve est faite : sans ce filtre, le test E2E échoue (redirection vers la connexion au lieu d'un refus).
    - **L'adresse imposée à la main n'était pas vérifiée.** `http://…` ou un port en trop donnaient une adresse projetée fausse.
    - **Un réseau de salle sans passerelle** (point d'accès local) faisait projeter `127.0.0.1`. Le PC cherche désormais aussi ses propres adresses.
    - **Les navigateurs demandaient `/favicon.ico` à chaque page**, ce qui produisait une erreur 404 rendue en entier. Une icône vide est déclarée.
    - **Un `PORT` exporté dans le shell** changeait le port en silence.
  - `/code-review`, écartés :
    - **Le journal en mode WAL de SQLite** : le test de charge passe sans lui, et les validations sont brèves.
    - **`STATIC_ROOT`, retiré** : `collectstatic` ne sert à rien ici. À revoir en I8 si l'hébergement l'exige.
    - **`DJANGO_DB_PATH`** : un module de réglages propre aux tests serait plus lourd pour le même effet.
  - **Agent `spec-auditor`** : 31 contre-épreuves, dont 26 détectées d'emblée. Deux réserves bloquantes :
    - l'adresse imposée (`ADRESSE=`) n'était prouvée par aucun test : ignorer l'option, dans le lanceur ou dans le Makefile, passait inaperçu ;
    - le filtre de l'espace enseignant n'était testé qu'en lecture (GET) : un filtre qui aurait laissé passer les envois de formulaire, donc les essais de mot de passe et le démarrage de la session, passait aussi. Le jeton CSRF n'aurait rien empêché, car le téléphone l'obtient sur la page étudiant.

    Ajouts : un test E2E lance `make classe ADRESSE=pc-prof.local`, et le téléphone envoie la connexion et le démarrage avec un jeton valide. Les pages d'erreur sont aussi vérifiées sur leur titre, et non plus sur le seul titre de l'onglet. J'ai rejoué les trois contre-épreuves (envois non filtrés, option ignorée par le lanceur, puis par le Makefile) : toutes détectées.

    Restent, non bloquants : le test de charge ne simule pas les interrogations d'état en même temps que les réponses, et 16 fils ne sont pas justifiés par un test (4 suffisent au test de charge).
  - `/security-review` : aucune vulnérabilité. Les fichiers servis par whitenoise se limitent aux fichiers statiques listés, le mode debug est toujours désactivé, et CSRF et la connexion sont inchangés.

### Ce qui a bien marché
- **Tester le vrai lanceur.** Les tests E2E lancent `make classe`, la commande même de l'enseignant, dans un processus à part, sur la base de test. Le téléphone ouvre l'adresse *lue au tableau*. Ils prouvent ensemble la désactivation du debug (le `.env` de test demande le debug), les fichiers statiques, le JavaScript du direct et l'adresse projetée.
- **Un test de charge simple, à l'échelle d'une classe.** 40 « téléphones » réduits à leurs requêtes HTTP, déclenchés au même instant par une barrière. Il a trouvé un vrai défaut dès son premier lancement, invisible avec quatre téléphones.
- **Les contre-épreuves faites au fil de l'eau** : SQLite sans `IMMEDIATE` et le filtre de l'espace enseignant retiré font chacun échouer un test.

### Ce que j'aurais dû savoir dès le départ
- **SQLite et la concurrence en écriture.** Avec une transaction ordinaire, un conflit de verrou échoue tout de suite au lieu d'attendre. Le mode `IMMEDIATE` (Django 5.1 et plus) est le réglage à prendre dès qu'un serveur à plusieurs fils écrit.
- **Hors debug, Django est muet.** Prévoir la journalisation des erreurs dès qu'on quitte le mode debug, sinon une erreur 500 ne laisse aucune trace.
- **Ouvrir un serveur au réseau, c'est l'ouvrir à tous les appareils du réseau**, y compris l'espace d'administration. Se demander dès la conception qui doit pouvoir joindre chaque partie de l'application.
- **Le hook Stop lance pytest.** Une vérification longue doit tourner au premier plan.

### Choix techniques et leur raison
- **waitress**, nouvelle dépendance d'exécution : le serveur de développement de Django n'est pas fait pour la production. waitress est en pur Python, fonctionne sous Windows (le PC de l'enseignant) et s'installe sans compilation. gunicorn ne fonctionne pas sous Windows. 16 fils au lieu de 4.
- **whitenoise**, nouvelle dépendance d'exécution : hors mode debug, Django ne sert plus les fichiers CSS et JS. whitenoise les sert depuis leurs dossiers (`WHITENOISE_USE_FINDERS`), sans étape `collectstatic` ni dossier à générer.
- **Un lanceur Python (`config/classroom.py`) plutôt qu'une commande `manage.py`** : le mode debug et l'adresse doivent être fixés *avant* le chargement des réglages, ce qu'une commande de gestion ne permet pas. Il fonctionne aussi sans make, sous Windows.
- **L'adresse du réseau local, détectée par la route par défaut** : une socket UDP « connectée » vers une adresse de documentation choisit la bonne interface, sans envoyer aucun paquet. L'adresse peut être imposée.
- **Le filtre de l'espace enseignant, par l'adresse de l'appareil** : waitress n'est derrière aucun mandataire, donc l'adresse de l'appareil est fiable. Ce filtre ne dépend d'aucun en-tête que le client pourrait falsifier.
- **Pages d'erreur en français** : sans le mode debug, ce sont les pages que voient les téléphones.

---

## R — Corrections issues d'un audit externe

### Objectif
En fin de projet, un relecteur **extérieur à mes sessions** a analysé le dépôt et mes journaux de session. Ses 7 constats portent sur ma méthode et mon environnement de travail, pas sur l'application : aucune exigence de SPEC.md ne change, et le numéro d'incrément de `pyproject.toml` reste 7. Le commanditaire m'a demandé de vérifier chaque constat avant de le corriger, de contester ceux qui me semblaient faux et de tout consigner ici.

Résultat : **aucun constat n'est faux.** J'en nuance trois sur des détails, sans en contester le fond. Tous décrivent des défauts que mes propres revues n'avaient pas vus, et deux contredisent ce que ce document affirmait.

### Les constats, vérifiés un par un

**1. Protection des secrets : exact.**
- *Vérifié.* `.claude/settings.json` fixait `UV_ENV_FILE=.env`, et un `uv run` avait bien la clé dans son environnement (contrôlé par un booléen, sans l'afficher). J'ai soumis 15 façons de lire le fichier au garde : 11 passaient (`base64`, `cp`, `dd`, `python3 -c`, etc.).
- *Nuance.* Le REX n'employait pas le mot « garantie », mais il listait ce refus parmi les garde-fous sans en donner la limite : l'effet est le même.
- *Relevé rassurant.* Aucune valeur de clé n'apparaît dans les journaux de session, sous-agents compris. Rien n'indique donc une fuite.
- *Correction.* Les vérifications n'utilisent plus la vraie clé : `make check`, `make verify`, la CI, les tests du mode classe et le shell de Claude Code chargent `.env.test`, versionné et sans valeur. Seuls `make run`, `make classe` et `make superuser` lisent `.env`.
- *Ce que la protection garantit vraiment, aujourd'hui :*
  - **Réel :** la clé n'entre jamais dans le dépôt (`.gitignore`, gitleaks en pre-commit et en CI, secret scanning de GitHub). L'outil Read refuse le fichier, par une règle de permission appliquée par Claude Code. Le fichier est illisible par les autres comptes de la machine (droits 600). Les vérifications ne chargent plus la clé.
  - **Anti-accident seulement :** le garde Bash refuse toute commande qui nomme `.env` en argument, sauf celles qui ne le lisent pas (`ls`, `test`, `git`, `make`, `uv`…). Il reste contournable : `python3 -c` qui ouvre le fichier passe, et un test épingle cette limite pour que personne ne la croie levée. Claude Code tourne avec mes droits sur la machine, donc **rien n'empêche techniquement un agent de lire `.env`** : l'interdiction tient à la consigne. De plus, `uv run` est autorisé sans confirmation.
  - **Enjeu.** La clé est locale et se régénère : elle signe les sessions de l'application sur un PC. La fuite serait à corriger, pas à réparer.

**2. Sandbox de Claude Code : exact, et écarté après essai.**
- *Vérifié.* Aucune mention dans les messages de l'incrément 0, ni dans le REX.
- *Ce qu'il apporterait.* Une vraie frontière au niveau du système pour les commandes Bash : secrets inaccessibles, écriture limitée au projet, réseau filtré. C'est précisément ce qui manque au constat 1.
- *Essais.*
  - Le vrai sandbox refuse de démarrer sur cette machine : `socat not installed`. Il faudrait l'installer en administrateur, hors de `make setup`. Sans l'option `failIfUnavailable`, la documentation précise que les commandes tournent alors **sans sandbox**, sans bloquer : une fausse sécurité.
  - Je n'ai donc pas pu tester son proxy réseau. J'ai reproduit le reste directement avec bubblewrap, son moteur sous Linux : `make verify-tests` dans une copie jetable, sans réseau, disque en lecture seule hors de la copie, `.env` masqué. **403 tests sur 404 passent**, Chromium compris, et `.env` est bien inaccessible.
  - Le seul échec est le test E2E de CLA-01 : un réseau isolé n'a pas d'adresse locale, or c'est exactement ce que ce test vérifie. `make verify`, donc la définition de « terminé », ne pourrait pas passer entièrement sous sandbox.
- *D'après la documentation.* Il ne couvre ni les outils de fichiers ni les hooks, donc ni Read ni le hook Stop. Sa sortie de secours (`dangerouslyDisableSandbox`) reste ouverte, sauf réglage contraire. Par défaut, il laisse lire `~/.ssh` et les fichiers d'identifiants. `gh` et `git push` demanderaient une liste de domaines, ou de sortir du sandbox.
- *Décision : écarté pour ce projet.* Le coût (dépendance système hors `make setup`, vérification à scinder, réglages d'écriture et de réseau) dépasse l'enjeu : plus aucune vérification n'a besoin de la clé, elle est locale et régénérable, le dépôt ne contient aucune donnée réelle, et `main` est protégée côté serveur.
- *Ce que j'accepte en l'écartant.* Il n'y a pas de frontière système : une commande malheureuse ou une instruction piégée agit avec mes droits, et les confirmations de Claude Code restent la seule barrière.
- *À réévaluer si :* l'hébergement en ligne (I8) introduit de vrais secrets, de vraies listes d'étudiants arrivent sur la machine de développement, ou des agents tournent sans surveillance.

**3. Arrêt après `/security-review` en I6 : exact.**
- *Vérifié.* Mon dernier message était le rapport de sécurité. Le commanditaire m'a relancé 33 minutes plus tard. Le REX I6 n'en parlait pas : c'est ajouté.
- *Correction.* Le hook Stop vérifie aussi la procédure. Il lit la branche, REX.md, l'état de la PR et les tags, et renvoie au travail tant qu'il reste une étape constatable. Le test rejoue l'arrêt réel de I6. Le skill `increment` dit aussi qu'un rapport de revue n'est jamais un message final.
- *Limite.* Le hook relance **une seule fois par arrêt**, et c'est voulu : sinon il deviendrait impossible de poser une question ou d'attendre la CI. C'est un rappel fort, pas un blocage. Il ne voit pas non plus les revues elles-mêmes : pour l'audit, il cherche la ligne « Audit spec-auditor : <commit> » dans la section du REX, que j'écris moi-même. C'est une déclaration, pas une preuve.

**4. Codes de retour masqués : exact, une nuance sur le second.**
- *Vérifié.* En I5, le commit `8dfdcda` est parti malgré « 1 failed ». En I6, l'`echo` écrivait fidèlement « exit 2 » dans le journal : c'est le statut de la commande entière qui était 0, et non le texte de l'`echo`. Le défaut est le même : le code de retour n'a pas survécu. J'ai rejoué le nouveau garde sur les 455 commandes shell des 4 sessions : 127 vérifications passées dans un pipe sans `pipefail`, dont 46 après l'incident de I5, et 49 suites qui auraient remplacé le code de retour. La leçon n'était consignée nulle part.
- *Correction.* Une règle dans CLAUDE.md, et un garde qui refuse une vérification (`make check`, `pytest`, `pyright`, `ruff`…) suivie d'un pipe sans `pipefail`, d'un `;` ou d'un `|| true`. Ce refus s'applique à mes propres commandes depuis cette section.
- *Limite.* C'est une analyse de la commande : un script écrit à part, ou une boucle `for`, y échappe.

**5. Tests « rouges » de I0 : exact, une nuance sur la citation.**
- *Vérifié.* Le journal montre `config/urls.py` copié de côté, vidé, 6 échecs constatés, puis le fichier rétabli. Les commits s'étalent bien sur 51 secondes.
- *Nuance.* Le REX disait « l'historique prouve qu'ils peuvent échouer », pas qu'ils avaient été écrits d'abord, et les 6 échecs étaient réels. Mais la phrase se présentait comme la preuve de « tests d'abord » : elle trompait, je l'ai corrigée.
- *Pour les autres incréments.* J'ai relevé dans les journaux les écritures de fichiers applicatifs avant chaque commit rouge, de I1 à I7 : aucune trouvée. Ce relevé est heuristique (outils d'édition et formes courantes d'écriture en shell), mais il va dans le bon sens. En revanche, la règle « le premier commit contient les tests » n'est pas littéralement suivie en I3, où un commit `ci:` les précède. Ce sont les journaux qui renseignent sur l'ordre d'écriture, pas git.

**6. Agent `spec-auditor` « en lecture seule » : exact.**
- *Vérifié.* Le même fichier disait « Tu ne modifies aucun fichier » et, plus bas, ordonnait de casser du code dans un worktree. 8 journaux de sous-agents contiennent un `git worktree add`.
- *Choix.* Le rendre réellement en lecture seule lui retirerait les contre-épreuves, qui ont trouvé de vrais défauts dans presque chaque incrément. Je garde donc ses droits et je dis la vérité.
- *Correction.* Sa description ne promet plus la lecture seule. `isolation: worktree` le fait démarrer dans une copie jetable, et il vérifie d'abord le commit audité. Après son passage, le skill contrôle que le dépôt principal n'a pas bougé.
- *Ce que cela garantit.* Son dossier de départ et un contrôle après coup. Il pourrait encore atteindre le dépôt principal par un chemin absolu : l'interdiction tient à la consigne.

**7. Dérive vers l'anglais : exact.**
- *Vérifié, par un comptage heuristique.* Dans la session des incréments 0 à 4, les messages en anglais passent de 0 sur 40 à 19 sur 40, puis 36 sur 40, 38 sur 40 et 28 sur 29. Les sessions suivantes, plus courtes, en comptent au plus 2 sur 40.
- *Cause probable, non prouvée.* Il n'y a eu aucun compactage. La dérive s'installe avec les prompts en anglais de `/simplify` et `/security-review`, quoique le tout premier message anglais les précède de quelques minutes. Le commanditaire, lui, écrivait en français.
- *Correction.* La règle 7 de CLAUDE.md couvre désormais la conversation, et SessionStart la rappelle. Aucun garde ne peut l'imposer : c'est une consigne.

### Défaut trouvé en plus de l'audit
Le REX I6 contenait un bloc de 7 lignes qui parlait du mode classe (`ADRESSE=`, filtre de l'espace enseignant). Il venait de l'incrément 7, collé au mauvais endroit par le commit `9111c39` ; `inc-6` ne le contient pas. Je l'ai retiré : le texte reste à sa place dans la section I7.

### Questions au commanditaire : toujours ouvertes
Le message de l'audit prévoyait les réponses à mes deux questions de l'incrément 7, mais ses deux champs sont restés à l'état de gabarit (`[OUI / NON, préciser]`, `[pas encore fait / fait, résultat : ...]`). Je ne les interprète pas.
- **Espace enseignant réservé au PC en mode classe.** Rien ne change, et SPEC.md le garde « à confirmer ».
- **Essai réel avec un téléphone sur le Wi-Fi.** Considéré comme non fait. Les tests E2E de CLA-01 tournent sur une seule machine, avec des téléphones émulés : ils ne disent rien de l'isolation d'un vrai Wi-Fi d'école, qui reste le principal risque en classe.

### Problèmes rencontrés
- **Le garde a analysé `2>&1` comme un séparateur de commandes.** Le `&` coupait la commande en deux : le test de pipe aurait regardé un « 1 » à la place de `make verify`. Ces redirections sont retirées avant l'analyse.
- **Mon propre test était trop strict.** Il interdisait « lecture seule » dans tout le fichier de l'agent, alors que celui-ci doit justement écrire qu'il ne l'est pas. Il porte maintenant sur la description, seule promesse faite à l'extérieur.
- **Mon premier comptage était faux, à 100 près.** J'ai d'abord annoncé 29 pipes, dont 5 après I5. Mon expression régulière s'arrêtait sur le `&` de `2>&1`, et donnait 0 pour la session même de l'incident, ce qui m'a alerté. Le chiffre juste vient du garde rejoué sur l'historique : 127, dont 46. Un outil de mesure se vérifie sur un cas dont on connaît la réponse.

### Ce qui a bien marché
- **Vérifier sur pièces avant de corriger.** Les journaux ont apporté des précisions que le seul énoncé des constats ne donnait pas : l'origine exacte du `exit 0`, et l'écart entre la citation et la phrase du REX.
- **Essayer au lieu de raisonner sur le sandbox.** Le test qui l'empêche de valider `make verify` n'apparaissait dans aucune documentation.
- **Écrire les tests d'abord, pour de vrai.** 49 échecs observés et commités avant toute correction, sur la leçon même du constat 5.

### Ce que j'aurais dû savoir dès le départ
- **Une affirmation de preuve se relit comme une exigence.** « L'historique prouve » et « en lecture seule » étaient plus forts que les faits. Écrire ce qu'un mécanisme garantit, ce qu'il ne garantit pas, et ce qui ne tient qu'à la consigne.
- **Un incident rattrapé reste à consigner.** Les deux codes de retour et l'arrêt de I6 ont été vus sur le moment, puis jamais écrits : c'est ainsi qu'une vérification a pu repasser 46 fois dans un pipe après le premier incident.
- **Une consigne ne suffit pas à une règle qui compte.** Pour chaque règle, se demander ce qui la fait respecter, puis dire honnêtement si rien ne le fait.
- **Un inventaire se confronte à la liste des fonctions de l'outil,** pas à ce dont on se souvient.
- **Un relecteur extérieur voit ce que mes revues ne peuvent pas voir.** Elles portent sur le diff. Aucune ne lit mes journaux, ni ne confronte ma méthode à ce que j'en dis.

### Choix techniques et leur raison
- **Aucune nouvelle dépendance.**
- **`.env.test` versionné plutôt qu'une clé éphémère en CI** : le même fichier sert partout, en local, en CI et dans les copies jetables, et un clone neuf peut tout vérifier sans générer de clé. Sa valeur ne protège rien, et son nom le dit.
- **Un incrément « R » sans exigence** : pas de test E2E marqué `spec`, car rien ne change pour l'utilisateur. Les comportements ajoutés sont des hooks, testés comme du code. Branche `inc/r-…`, tag `inc-r`, reconnus par le garde et le hook Stop.
