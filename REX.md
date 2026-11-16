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
| I8 | Hébergement en ligne (conditionnel, selon la décision du professeur). *Le numéro a ensuite servi au retour du test réel : voir la section I8. L'hébergement reste conditionnel et sera numéroté le moment venu ; les mentions « I8 » de l'hébergement dans les sections plus anciennes datent de ce plan.* |

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
En fin de projet, un relecteur **extérieur à mes sessions** a analysé le dépôt et mes journaux de session. Ses 7 constats portent sur ma méthode et mon environnement de travail, pas sur l'application : aucune exigence de SPEC.md ne change, et le numéro d'incrément de `pyproject.toml` reste 7. Deux retouches de l'application viennent de l'audit interne qui a suivi, sans rien changer à son fonctionnement normal : le décompte du navigateur entre deux interrogations, et la lecture de l'horloge dans `add_time` (voir plus bas). Le commanditaire m'a demandé de vérifier chaque constat avant de le corriger, de contester ceux qui me semblaient faux et de tout consigner ici.

Résultat : **aucun constat n'est faux.** J'en nuance trois sur des détails, sans en contester le fond. Tous décrivent des défauts que mes propres revues n'avaient pas vus. Le constat 5 contredit directement ce document, le constat 6 contredit le fichier de l'agent, et le constat 1 nuance ce que ce document laissait entendre.

### Les constats, vérifiés un par un

**1. Protection des secrets : exact.**
- *Vérifié.* `.claude/settings.json` fixait `UV_ENV_FILE=.env`, et un `uv run` avait bien la clé dans son environnement (contrôlé par un booléen, sans l'afficher). J'ai soumis 15 façons de lire le fichier au garde : 11 passaient (`base64`, `cp`, `dd`, `python3 -c`, etc.).
- *Nuance.* Le REX n'employait pas le mot « garantie », mais il listait ce refus parmi les garde-fous sans en donner la limite : l'effet est le même.
- *Relevé rassurant.* Aucune valeur de clé n'apparaît dans les journaux de session, sous-agents compris. Rien n'indique donc une fuite.
- *Correction.* Les vérifications n'utilisent plus la vraie clé : `make check`, `make verify`, la CI, les tests du mode classe et le shell de Claude Code chargent `.env.test`, versionné et sans valeur, et un test l'impose au mode classe. Seuls `make setup`, `make run`, `make classe` et `make superuser` lisent `.env`.
- *Ce que la protection assure vraiment, aujourd'hui :*
  - **Imposé par un outil :** `.gitignore` écarte le fichier. L'outil Read le refuse, par une règle de permission de Claude Code (règle présente, non éprouvée : l'essayer reviendrait à lire le fichier). Il est illisible par les autres comptes de la machine (droits 600). Les vérifications ne chargent plus la clé, et un test l'impose.
  - **Détecté, pas empêché :** gitleaks bloque un commit contenant la clé une fois `make setup` fait (l'audit l'a vérifié avec une fausse clé). En CI, il ne la voit qu'après le push. Le secret scanning de GitHub ne la reconnaîtrait probablement pas : c'est une chaîne aléatoire, et les motifs hors fournisseurs sont désactivés sur ce dépôt (déduction, non testée).
  - **Anti-accident seulement :** le garde Bash refuse toute commande qui nomme `.env` en argument ou le charge par `uv run --env-file`, sauf quelques commandes autorisées, dont certaines peuvent le lire (`git commit -F .env`, `make -f .env`). Il reste contournable : `python3 -c` qui ouvre le fichier passe, comme `bash -c`, `cat .en?` ou une substitution dans une chaîne, et un test épingle cette limite pour que personne ne la croie levée. Claude Code tourne avec mes droits sur la machine, donc **rien n'empêche techniquement un agent de lire `.env`** : l'interdiction tient à la consigne. De plus, `uv run` est autorisé sans confirmation.
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
- *Vérifié.* En I5, le commit `8dfdcda` est parti malgré « 1 failed ». En I6, l'`echo` écrivait fidèlement « exit 2 » dans le journal : c'est le statut de la commande entière qui était 0, et non le texte de l'`echo`. Le défaut est le même : le code de retour n'a pas survécu. J'ai rejoué le nouveau garde sur les 455 commandes shell des 4 sessions : 124 vérifications passées dans un pipe sans `pipefail`, dont 43 après l'incident de I5, et 55 suites qui auraient remplacé le code de retour. La leçon n'était consignée nulle part.
- *Correction.* Une règle dans CLAUDE.md, et un garde qui refuse une vérification (`make check`, `pytest`, `pyright`, `ruff`…) suivie d'un pipe sans `pipefail`, d'un `;` ou d'un `|| true`. Ce refus s'applique à mes propres commandes depuis cette section.
- *Limite.* C'est une analyse de la commande : un script écrit à part, une boucle `for`, un `bash -c`, un bloc `{ make check; } | tail`, `uvx` ou `xargs` y échappent. Elle accepte aussi `exit $code` sans vérifier que `$code` vient bien de la vérification.

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

Une question nouvelle, née de cet audit :
- **L'horloge du PC de classe.** Le déroulement d'une session se calcule à partir de l'horloge système du serveur. Si elle recule de 2 s, comme sur ce PC de développement :
  - le compte à rebours affiché remonte (essayé sous `make classe` : de 83 à 86 s) ;
  - la liste des connectés peut s'inverser (observé dans un test, sans l'horloge stable) ;
  - le créneau précédent peut revenir brièvement sur les téléphones, et une réponse donnée juste après un changement de créneau peut être refusée (déduit du code et des échecs de tests, pas essayé sous `make classe`).

  Je ne sais pas si un PC sous Windows, sans WSL2, a ce défaut : à contrôler sur le vrai PC de classe avant une évaluation notée. Le corriger pour de bon, si besoin, est une décision de conception : ne plus calculer le déroulement sur l'horloge système.

### Problèmes rencontrés
- **Le garde a analysé `2>&1` comme un séparateur de commandes.** Le `&` coupait la commande en deux : le test de pipe aurait regardé un « 1 » à la place de `make verify`. Ces redirections sont retirées avant l'analyse.
- **Mon propre test était trop strict.** Il interdisait « lecture seule » dans tout le fichier de l'agent, alors que celui-ci doit justement écrire qu'il ne l'est pas. Il porte maintenant sur la description, seule promesse faite à l'extérieur.
- **Mon premier comptage était faux, à 100 près.** J'ai d'abord annoncé 29 pipes, dont 5 après I5. Mon expression régulière s'arrêtait sur le `&` de `2>&1`, et donnait 0 pour la session même de l'incident, ce qui m'a alerté. Le chiffre juste vient du garde rejoué sur l'historique : 124, dont 43. Un outil de mesure se vérifie sur un cas dont on connaît la réponse.

### Ce que les revues ont trouvé
Même sur un incrément de correction, les revues ont trouvé de vrais défauts, dont un que j'avais introduit en appliquant la revue précédente.
- **`/simplify`** (quatre angles).
  - Retenu : une seule analyse de la commande, les préfixes retirés pour toutes les règles (`timeout 5 git push --force` et `uv run cat .env` passaient), la règle sur `.env` inversée au lieu d'une liste de lecteurs, le hook Stop découpé, `gh` limité à 5 s.
  - Retenu, le plus utile : l'audit était « vérifié » par la présence du mot `spec-auditor`, qui figurait déjà dans le titre de mon constat 6. Le contrôle n'aurait rien vu ici. Il exige maintenant une ligne dédiée.
  - Écarté : **un rappel par état plutôt que par arrêt**, qui économiserait des tours. L'arrêt de I6 survenait après une revue sans commit : il repasserait sans rappel.
  - Écarté : **`pipefail` pour toute la session** par `CLAUDE_ENV_FILE`, qui traiterait la cause plus à la racine. Je ne peux pas l'essayer dans une session déjà ouverte, et `git log | head` échouerait.
  - Écarté : le tag posé par la CI (hors périmètre, droits d'écriture à donner au workflow), et un module commun aux hooks (quelques lignes dupliquées coûtent moins qu'un import de plus entre scripts autonomes).
- **`/security-review`.** Une régression, que j'avais introduite en appliquant `/simplify` : un `<<` dans une chaîne, ou un here-string `<<<`, était pris pour un heredoc et masquait les lignes suivantes. `echo "<<X"` puis `git push --force` passait, alors que `main` le refuse. J'ai reproduit les 10 cas en tests rouges avant de corriger. Aucune vulnérabilité sur le reste. `.env.test` n'atteint ni `make classe` ni `make run`. Seul un `uv run python -m config.classroom` lancé depuis le shell de Claude Code la chargerait, avec très peu d'effet : les sessions sont stockées en base, leur cookie n'est pas signé par cette clé.
- **`/code-review`.** 10 constats, 31 cas reproduits en tests rouges :
  - masquage plus loin dans la chaîne (`make check && echo ok; echo fin`), `make check &`, `exit 0` accepté comme un code honnête, `set +o pipefail` pris pour une activation ;
  - suite de ligne (`git push \` puis `--force` à la ligne) : l'option échappait au garde, et cela existait déjà sur `main` ;
  - préfixes `env -i`, `timeout -k`, `time`, `!` ;
  - `git diff --no-index /dev/null .env` passait, et aurait affiché la clé sans confirmation ;
  - une PR fermée sans fusion ne laissait aucun manque ;
  - `make accept INC=r` est impossible (`--spec-inc` attend un entier) : un incrément sans exigence se vérifie avec le dernier numéro.
- **Le garde m'a refusé trois fois** pendant ces corrections. Une fois à raison (un `; echo` après pytest), deux fois à tort, parce que ma généralisation traitait tout pipe de la chaîne comme un masquage, alors que la forme recommandée par CLAUDE.md en contient un plus loin. Corrigé, avec ce cas en test.
- **Le hook Stop s'est déclenché en conditions réelles**, à chaque attente de sous-agent. Il coûte un tour de plus par attente. C'est le prix du rappel, et je le garde.
- **Le skill `/security-review` demande que la réponse finale soit son rapport « et rien d'autre ».** C'est la cause probable de l'arrêt de I6, et cette consigne s'est représentée ici. Je n'ai pas clos mon travail sur ce rapport.
- **Contre-audit de `spec-auditor` : l'horloge de cette machine recule.** Après mes corrections, `make accept` échouait encore 3 fois sur 4, sur 3 tests différents.
  - *Mesuré, et reproduit par ma propre sonde :* l'horloge système recule d'environ 1,4 à 2 s toutes les 32 s (sauts à 31 s, 63 s et 95 s chez moi ; 266 sauts en 2 h 20 chez l'auditeur, tous en arrière, de 0,5 à 2,8 s). `systemd-timesyncd` corrige à chaque interrogation un écart qui revient ensuite, sous WSL2.
  - *Conséquence :* tout test à moins de 2 s de marge échoue au hasard. Le compte à rebours remontait de 30 à 32 s, une réponse était refusée juste après `jump_to(61)`, et deux noms s'inversaient. Mes `make verify` verts tenaient donc en partie à la chance, et la CI, sur une autre machine, n'en voyait rien.
  - *Ma cause écrite (le délai de Playwright) était fausse :* je l'avais déduite d'un seul test, sans mesurer. Les échecs intermittents de I5 et I6 (« le téléphone saute le créneau ») ont peut-être la même origine ; je ne peux plus le vérifier.
  - *Corrigé dans le dépôt :* le serveur de test lit une horloge sans saut, ce qui rend les tests concernés insensibles à ces reculs. Les tests du mode classe gardent la vraie horloge, car leur serveur est un processus à part. Le décompte du navigateur devient monotone, mais seulement entre deux interrogations.
  - *Ce que cela ne corrige pas :* le serveur de l'application lit toujours l'horloge système, et l'écran se recale sur lui chaque seconde. **Le compte à rebours affiché peut donc encore remonter** : l'auditeur l'a vu passer de 83 à 86 s, au tableau et sur le téléphone, sous `make classe`. Mon commit et ma première rédaction affirmaient le contraire : j'avais jugé sur un test qui coupe justement ces interrogations. Voir les questions ouvertes.
  - *Résultat, sous de vrais sauts :* `make accept INC=7` passe 7 fois sur 8, et `make verify` passe. Retirer l'horloge stable fait échouer 2 passages sur 10 des modules I3, I5 et I6, avec la signature de l'horloge (`15 <= 14.29`, noms inversés) ; avec elle, aucun échec dans ces modules sur 9 passages. L'écart est modeste, mais il va dans le bon sens. Décaler une échéance de 1 s, dans un sens ou l'autre, reste détecté : l'horloge stable ne masque pas ce défaut.
  - *Le passage en échec l'est pour une autre raison :* le réseau de ce PC. Sans route, le mode classe y annonce `127.0.0.1`, et le test de CLA-01 tombe. Le lien est une déduction solide (11 pertes de route relevées juste après, pas pendant) et non une observation directe. Ce test dépend donc du réseau du PC : son échec est lisible, et ce n'est pas un faux vert.
- **Verdict final de `spec-auditor`, après quatre passages :** aucune réserve bloquante. Le premier a trouvé 4 réserves, le deuxième l'horloge, le troisième le compte à rebours qui remonte, et le quatrième a confirmé les corrections. Chaque fois, j'avais cru le sujet réglé. Seules les précisions de rédaction qu'il a demandées et cette section ont changé depuis le commit audité.

Audit spec-auditor : d62fda7c8b46680e8756e68db29bee09ea6d0890

- **Un test du compte à rebours ne savait pas échouer.** Mon premier essai passait sur le code non corrigé : l'interrogation de l'état recalait le minuteur avant ma lecture. Le test coupe maintenant ces interrogations, et il est rouge 5 fois sur 5 sur l'ancien code.
- **Agent `spec-auditor`.** Première exécution dans sa copie jetable : le dossier et le commit étaient bons, et le dépôt principal n'a pas bougé. Plus de 80 contre-épreuves, avec 4 réserves bloquantes :
  - **Un test intermittent, antérieur à R.** `test_added_time_in_real_time` échouait 4 fois sur 8 chez lui, au commit de base comme sur la branche, alors que la CI et mes `make verify` passaient. J'ai d'abord accusé le délai de Playwright, et c'était faux : voir le paragraphe sur l'horloge, ci-dessus. La mesure du test date désormais le rechargement de la page, et sa borne basse passe de 13,5 s à 15 s exactes.
  - **Rien ne protégeait la correction du constat 1 en mode classe.** Retirer `ENV_FILE=.env.test` du test ne faisait rien échouer : le Makefile générait sans bruit un `.env`. Sur un poste de développement, le test aurait chargé la vraie clé.
  - **Le câblage du hook Stop n'était testé qu'à moitié.** Ne plus lire le REX, ne plus interroger `gh`, ne plus traiter main ou ne plus reconnaître `inc/r-…` : aucun test ne tombait. La ligne d'audit acceptait aussi une mention en milieu de phrase, soit le défaut même que `/simplify` venait de signaler. Ajout de tests de bout en bout du hook, avec un faux `gh`.
  - **Des surestimations dans ce document** : « la clé n'entre jamais dans le dépôt », le secret scanning cité comme protection, `uv` présenté comme ne lisant pas `.env`, et `make setup` oublié. Elles sont corrigées, et le garde refuse maintenant `uv run --env-file .env`, qu'aucune vérification n'utilise plus.
  - **Observation non élucidée :** il a reçu un CLAUDE.md périmé (8 règles, `UV_ENV_FILE=.env`), alors que son commit en contenait 10. Un sous-agent peut donc ne pas voir les règles ajoutées pendant la session en cours.

### Ce qui a bien marché
- **Vérifier sur pièces avant de corriger.** Les journaux ont apporté des précisions que le seul énoncé des constats ne donnait pas : l'origine exacte du `exit 0`, et l'écart entre la citation et la phrase du REX.
- **Essayer au lieu de raisonner sur le sandbox.** Le test qui l'empêche de valider `make verify` n'apparaissait dans aucune documentation.
- **Écrire les tests d'abord, pour de vrai.** 49 échecs observés et commités avant toute correction, sur la leçon même du constat 5.

### Ce que j'aurais dû savoir dès le départ
- **Une affirmation de preuve se relit comme une exigence.** « L'historique prouve » et « en lecture seule » étaient plus forts que les faits. Écrire ce qu'un mécanisme garantit, ce qu'il ne garantit pas, et ce qui ne tient qu'à la consigne.
- **Un incident rattrapé reste à consigner.** Les deux codes de retour et l'arrêt de I6 ont été vus sur le moment, puis jamais écrits : c'est ainsi qu'une vérification a pu repasser 43 fois dans un pipe après le premier incident.
- **Une consigne ne suffit pas à une règle qui compte.** Pour chaque règle, se demander ce qui la fait respecter, puis dire honnêtement si rien ne le fait.
- **Un inventaire se confronte à la liste des fonctions de l'outil,** pas à ce dont on se souvient.
- **Un test intermittent se mesure avant de s'expliquer.** J'ai réparé une cause plausible, sans sonde, et elle était fausse. Une explication qui tient sur un seul test ne vaut rien tant qu'elle n'a pas été confrontée aux échecs des autres.
- **L'horloge d'une machine n'est pas une donnée fiable.** Une application qui calcule des échéances doit le prévoir, et sa suite de tests aussi.
- **Un relecteur extérieur voit ce que mes revues ne peuvent pas voir.** Elles portent sur le diff. Aucune ne lit mes journaux, ni ne confronte ma méthode à ce que j'en dis.

### Choix techniques et leur raison
- **Aucune nouvelle dépendance.**
- **`.env.test` versionné plutôt qu'une clé éphémère en CI** : le même fichier sert partout, en local, en CI et dans les copies jetables, et un clone neuf peut tout vérifier sans générer de clé. Sa valeur ne protège rien, et son nom le dit.
- **Un incrément « R » sans exigence** : pas de test E2E marqué `spec`, car rien ne change pour l'utilisateur. Les comportements ajoutés sont des hooks, testés comme du code. Branche `inc/r-…`, tag `inc-r`, reconnus par le garde et le hook Stop.

---

## I8 — Retour du test réel : QR codes

### Objectif
Traiter la première moitié du retour du commanditaire après un test réel : retirer le QR code de fin (FIN-01), ajouter un QR code au tableau pour rejoindre la session (SES-05), et consigner dans SPEC.md ses réponses et les questions ouvertes. Le numéro I8 était réservé à l'hébergement en ligne, resté conditionnel : il sera numéroté le moment venu.

**Découpage.** Deux incréments : I8 pour les QR codes, I9 pour l'affichage (énoncés au tableau seulement, N = 4 par défaut). Les deux QR codes vont ensemble : les séparer aurait obligé à retirer `segno`, zxing-cpp et Pillow, puis à les remettre.

**Réponses du commanditaire, reportées dans SPEC.md.**
- Espace enseignant réservé au PC en mode classe : oui, définitivement.
- Parcours complet réussi avec un vrai téléphone sur un Wi-Fi domestique, serveur lancé depuis Windows, hors WSL. C'est sa déclaration, je ne l'ai pas observé. Le Wi-Fi de l'école reste à tester.
- Questions restées ouvertes à ma connaissance : l'horloge du PC de classe et le compte à rebours qui peut remonter (section R). Son essai ne les tranche pas.

### Problèmes rencontrés
- **Le QR code de fin n'avait pas de but établi, et j'en suis en partie responsable.** Je l'ai livré en I6 en détaillant son contenu, sans jamais demander à quoi il servirait ni qui le lirait. Il a fallu un test réel et une discussion avec le professeur pour le retirer. Une exigence dont personne ne sait dire l'usage mérite une question, même si elle figure dans la spec.
- **Retirer des tests retire aussi ce qu'ils protégeaient : réserve bloquante de `spec-auditor`.** Le test du reçu était le seul à vérifier, au niveau du participant, qu'un « +10 s » ne change pas la question attribuée. En le supprimant avec FIN-01, j'ai perdu cette protection sans le voir, alors que `make verify` restait vert. Un nouveau test la rétablit (`test_added_time_keeps_the_rotation`).
- **Mon test de FIN-02 ne vérifiait pas tout son énoncé : autre réserve bloquante.** « Ni réponses » était écrit dans la spec, mais le téléphone du test ne répondait jamais, si bien qu'afficher ses réponses à la fin ne faisait rien échouer. Il répond désormais. Autre faiblesse, non bloquante : `get_by_role("img")` ignore une image à `alt` vide. Les tests de disparition regardent maintenant toute image de la page.
- **Ma correction d'une faiblesse non bloquante a créé une réserve bloquante : deuxième passage de `spec-auditor`.** Pour voir les images à `alt` vide, j'avais limité la recherche à `<main>`. Une image placée hors de `main`, détectée avant, ne l'était plus. Une régression de test, introduite en corrigeant un test. Le correctif, proposé par l'auditeur et relu avant application, cherche dans toute la page, et le texte exact se vérifie sur `body`.
- **Mon test de rotation promettait plus qu'il ne vérifiait : autre réserve de ce passage.** Avec deux questions et le seul rang 0, il laissait passer un décalage par les secondes ajoutées (10 est multiple de 2) ou un produit (rang 0). Ce trou existait déjà sur main, l'ancien test du reçu ayant les mêmes données : ce n'est pas une régression. L'auditeur l'a classé bloquant parce que ce test venait lever une réserve. Le test passe à 3 questions, 2 participants et 2 ajouts, avec des valeurs attendues écrites en dur. Il a aussi signalé, sans le juger bloquant, que rien ne vérifiait la couleur du téléphone après un ajout, angle mort lui aussi antérieur à I8 : c'est corrigé au passage.
- **Une reprise de l'auditeur n'a rien pu vérifier.** Sa copie jetable est supprimée à sa remise, et le commit n'était pas encore poussé. Il a refusé de rendre un verdict, à juste titre. Pour un nouveau passage, il faut relancer l'agent dans une copie neuve, pas le reprendre.
- **La spec promettait au retardataire ce que l'écran ne donne pas.** J'avais écrit qu'il « passe par l'adresse et le code », or le tableau en déroulement n'affiche que le code (`/code-review`). Corrigé dans la spec. C'est la conséquence, acceptée par le commanditaire, de sa décision de n'afficher le QR code qu'avant le démarrage : l'option qu'il a retenue le disait.
- **Le réseau du PC a de nouveau faussé une lecture.** Au moment des tests rouges, le test de CLA-01 a échoué sur `127.0.0.1`, et non sur le QR code attendu. Le piège était documenté : la route était revenue quand j'ai vérifié, et le relancer a donné l'échec attendu. Le test de l'adresse du réseau local existe désormais aussi sans dépendre du réseau (`settings.JOIN_URL` fixé).
- **Le garde a refusé deux de mes commandes** (`;` puis pipe après un pytest, sans `pipefail`). Il a joué son rôle : rien n'est parti avec un code de retour effacé.

- **Un auditeur a tenté de nommer `.env`.** Au troisième passage, une commande composée de `spec-auditor` contenait `ls .env .env.test`, pour en vérifier l'existence. Le garde l'a refusée, et il dit ne pas avoir lu le fichier ni retenté. C'est sa déclaration, et je n'ai rien observé qui la contredise. La règle ne tient toujours qu'à la consigne et au garde, qui ne couvre pas toutes les formes.
- **Verdict final de `spec-auditor`, après trois passages :** aucune réserve bloquante au commit 4136116. Le premier a rendu 2 réserves bloquantes, le deuxième 2 autres, et le troisième a confirmé le correctif et les contre-épreuves (`make verify` compris). Il a limité ce dernier passage à ces points, sans refaire les autres exigences ni relire SPEC.md, couverts par le premier. Depuis ce commit, seule cette section a changé.

Audit spec-auditor : 4136116b5de16bfccd98773409596d86bcd4ba54

### Ce qui a bien marché
- **Poser deux questions avant d'écrire les tests** : quand le QR code est visible, et ce que recouvre « modifiable ». Les réponses ont évité de construire un QR code permanent et une modification en cours de session.
- **Lire le QR code comme un vrai lecteur** (capture, décodage, ouverture de l'adresse sur un autre appareil), y compris en vrai mode classe. Le QR code et le texte projeté ne peuvent pas diverger : ils partent de la même adresse.
- **Les passages successifs de `spec-auditor`.** Les contre-épreuves que j'avais rejouées moi-même sur ma première correction étaient toutes détectées, et le passage suivant a pourtant trouvé deux réserves. Rejouer ses propres cas ne suffit pas à déclarer un sujet réglé.

### Ce que j'aurais dû savoir dès le départ
- **Avant de supprimer un test, se demander ce qu'il est le seul à vérifier.** Une couverture de code à 98 % ne le dit pas : la ligne restait couverte par d'autres tests, sans que ce comportement y soit contrôlé.
- **Chaque mot d'une exigence négative demande une précondition qui pourrait le contredire** : pour « ni réponses », il faut une réponse.
- **Une donnée de test trop petite vide un test de son sens** : un rang 0 annule un produit, et n = 2 divise 10. Choisir des valeurs qui distinguent les erreurs plausibles.

### Choix techniques et leur raison
- **Aucune nouvelle dépendance.** `segno` change de rôle (QR code de jonction), et zxing-cpp et Pillow restent en test pour le lire.
- **Le QR code mène à `/s/<code>/`**, l'écran de session existant : aucune nouvelle route, et un téléphone déjà identifié y retrouve son écran (ETU-03).
- **L'image est intégrée à la page (SVG en data URI)**, déjà permise par la CSP. Elle n'est calculée qu'au rendu de la page en attente, jamais à l'interrogation de l'état chaque seconde.
- **Le QR code se limite à la moitié de la hauteur d'écran**, pour laisser sa place à la liste des connectés sur un projecteur 1024x768.

### Ce qui n'est garanti que par la consigne ou reste à vérifier
- **Lecteurs à navigateur intégré (SPEC §5).** L'identité vit dans le cookie du navigateur qui a validé le numéro. Une application qui ouvre le lien dans son propre navigateur pourrait la perdre, avec un numéro resté lié à ce premier « appareil ». Non observé, et les tests ne peuvent pas le voir : à essayer sur de vrais téléphones.
- **La lecture depuis la salle.** Un test impose une taille minimale et décode une capture nette. Il ne dit rien d'une photo prise à 10 mètres d'un projecteur.
- **Sans réseau, ou en mode développement ouvert en `localhost`,** le QR code contient une adresse que le téléphone ne peut pas joindre, comme le texte projeté. Écarté : le mode classe l'annonce dans le terminal.

---

## I9 — Retour du test réel : affichage, formes et palette

### Objectif
Traiter la seconde moitié du retour du commanditaire après le test réel, complétée par ses précisions du 12 novembre, après discussion avec le professeur :
- tableau limité aux énoncés, téléphone limité aux propositions (AFF-01), et 4 questions à la fois par défaut (SES-06) ;
- mention des questions à réponses multiples au tableau (AFF-02) ;
- une forme par couleur, en plus du numéro (AFF-03), et une palette lisible par les daltoniens et sur un vidéoprojecteur (AFF-04) ;
- ordre des propositions propre à l'étudiant, stable, sans effet sur la note (ETU-05, précisée).

Il fallait aussi consigner dans SPEC.md, sans rien implémenter : l'absence de correction en classe, l'horloge stable sous Windows, les retardataires sur copie papier, le réseau eduroam (risque principal, non testé) et le prochain incrément (import AMC, en attente d'un fichier d'exemple).

**Déroulé.** La branche existait déjà : une session précédente, le 8 novembre, avait commité les tests rouges puis le code d'AFF-01 et SES-06, sans section de REX et sans pousser. J'ai repris sur cette base. Le message de ce commit annonce des tests rouges, mais je n'ai pas vu cet échec moi-même, et l'historique ne prouve que l'ordre des commits.

**Questions posées avant d'écrire les tests**, avec leurs réponses :
- Palette : celle d'Okabe et Ito, proposée avec ses mesures (voir ci-dessous), est retenue.
- Forme de la mention « multiple » : « Plusieurs réponses possibles », en texte seul. Le ♣ d'AMC n'a pas été retenu.
- Ordre des propositions : il était déjà propre à l'étudiant depuis I4. J'ai expliqué que l'application ne sait pas qui est assis à côté de qui, et qu'avec 4 propositions, deux étudiants qui ont la même question voient la bonne réponse au même endroit 1 fois sur 4. Une « répartition équilibrée » entre étudiants connectés à la suite n'aiderait que si les voisins de table se connectaient l'un après l'autre. Le tirage au hasard est conservé.

### Évaluation de la palette
- **Méthode.** Écart CIEDE2000 entre chaque paire de couleurs, en vision normale et en simulation de protanopie, deutéranopie et tritanopie (matrices de Machado et al., 2009, sévérité maximale). S'y ajoutent les niveaux de gris (achromatopsie, photo en noir et blanc) et un projecteur délavé, modélisé par un voile de lumière ambiante, seul et combiné à la deutéranopie. C'est un modèle, pas une mesure sur un vrai projecteur.
- **L'ancienne palette** confondait le jaune et l'orange (1 et 5) : écart de 4,5 en deutéranopie, 3,3 sur projecteur délavé. Elle confondait aussi le bleu et le violet (2 et 6) en protanopie (4,9). Ses six couleurs avaient presque la même luminosité (écart de 0,2 en gris). Ses quatre premières tenaient, sauf en gris.
- **Recherche.** Une optimisation libre sur la grille des couleurs donnait des couleurs criardes ou presque blanches, inutilisables comme fond. Le meilleur sous-ensemble de palettes reconnues (Okabe et Ito, Paul Tol) en texte sombre seul plafonnait à un écart de 6,3. Accepter un texte blanc sur une couleur foncée élargit l'espace, et la palette d'Okabe et Ito l'emporte.
- **Palette retenue, ordonnée pour N = 4** : jaune, bleu, vert bleuté, bleu ciel, pourpre, orange. Pour les 4 premières, l'écart minimal vaut 8,4 sur toutes les conditions et 10,1 en gris. Sur les 6, il vaut 7,8 hors niveaux de gris, contre 3,3 auparavant. En gris, 3/5 et 4/6 restent proches : la forme et le numéro les départagent.
- **Coût :** texte blanc sur le bleu, et un contraste de 5:1 environ sur 2, 3 et 5, au lieu de 7:1. C'est au-dessus de 4,5:1, le seuil pour un texte courant (WCAG AA), et l'énoncé projeté est un gros texte.
- **Vérification visuelle.** Simulation appliquée à une capture réelle du tableau à 6 couleurs : en protanopie, deutéranopie, tritanopie et niveaux de gris, les 4 premières cartes restent distinctes. Au-delà, 5 et 6 se rapprochent en tritanopie, comme mesuré.

### Problèmes rencontrés
- **La partie « contraste » d'AFF-04 n'a pas été vue rouge avant le code.** Le test s'arrêtait d'abord sur la palette, et j'ai corrigé dans le même temps le texte gris et le bouton d'effacement posés sur la couleur. Pour vérifier que cette partie sait échouer, j'ai fait deux contre-épreuves après coup, sans les présenter comme un échec observé avant le code. Sans les correctifs, le test tombe sur le téléphone bleu (contraste de 1,2). Avec un texte sombre sur le bleu, il tombe au tableau (3,4).
- **Les deux tests ajoutés pour ETU-05 passent dès leur écriture.** Le comportement existe depuis I4 : ce sont des garde-fous, pas des tests rouges. Le premier, sur le retour à la session (code ressaisi, nouvel onglet), a ensuite rejoint le test ETU-05 d'I4, qu'il doublait (`/simplify`). Le second distingue sûrement la place à l'écran de la proposition par la lettre du CSV d'un étudiant qui choisit une proposition affichée ailleurs qu'à sa place. Une première version comptait aussi sur la place de la bonne réponse, ce qui l'aurait fait échouer 1 fois sur 64 : je l'ai retirée avant le commit.
- **La forme a cassé un test de SES-05 (I8).** Il comptait toute image du tableau en déroulement pour vérifier que le QR code avait disparu. Ma première correction attendait exactement une image, la forme de la couleur 1 : le test d'I8 dépendait alors des formes d'I9. Sur la remarque de `/simplify`, il ignore désormais les formes (`svg.shape`) et n'attend aucune autre image. Ce qu'il laisse passer : un QR code qui serait dessiné comme une forme de couleur, cas que je ne juge pas réaliste.
- **Le texte « Couleur N » doit rester seul dans son élément.** La forme placée dans le même paragraphe empêchait les tests de lire le numéro du téléphone. Le numéro est désormais dans son propre élément, à côté de la forme.
- **Une image d'analyse écrite dans le dépôt.** Mon script de comparaison des palettes a enregistré son image dans le dossier courant, à la racine du dépôt. Je l'ai déplacée dans le scratchpad aussitôt, avant tout commit, et vérifié que `git status` était vide.
- **Le garde a refusé deux de mes commandes** : des contre-épreuves enchaînées par `;`, puis un pipe sans `pipefail`. Je les ai relancées une par une, chacune avec son code de retour.
- **Défaut antérieur vu au contrôle visuel :** sur le téléphone, une case ou un bouton radio rétrécissait quand la proposition tenait sur plusieurs lignes. Une ligne de style le corrige.

### Ce que les revues ont trouvé
- **`/simplify`, quatre relecteurs.** Rien de bloquant : surtout des doublons dans les tests.
  - Corrigé :
    - téléchargement du CSV et attente d'une réponse enregistrée mis en commun avec I6 ;
    - démarrage par l'aide `started` ;
    - téléphones inutiles retirés du test AFF-02 ;
    - AFF-03 et AFF-04 réunis dans un même test, ce qui évite de construire deux fois une session à six téléphones ;
    - silhouettes lues par différence avec le fond, et couleurs comparées avec Pillow ;
    - fond propre au bouton secondaire, plutôt qu'une exception sur les pages colorées ;
    - taille des cases fixée dans la règle commune ;
    - `Session.start` ne renvoie plus un booléen qu'aucun appelant ne lit depuis le retrait du bandeau « Session démarrée ».
  - Contre-épreuve refaite après la nouvelle lecture des silhouettes : une étoile dessinée comme un rond fait échouer le test (recouvrement de 98 %).
  - Écarté :
    - la correspondance couleur → forme reste dans le gabarit ;
    - pas de variables CSS par couleur : le test de contraste couvre déjà les six couleurs ;
    - le `<span>` autour du numéro reste nécessaire pour lire « Couleur N » ;
    - le test SES-06 garde son remplissage du formulaire à la main, qui vérifie la valeur affichée avant l'envoi ;
    - pas de constructeur de session commun : il toucherait des tests d'autres incréments pour un gain faible.

- **`/code-review`, sept constats.**
  - **Le bouton « Effacer ma réponse » inactif était illisible sur une couleur.** Son opacité de 0,4 donnait un contraste de 1,6 à 2,1. Mon test ne pouvait pas le voir pour deux raisons : il mesurait après une réponse, quand le bouton est actif, et son relevé ignorait l'opacité. Le bouton inactif est désormais gris sur blanc. Le relevé compose l'opacité, et le test mesure avant et après la réponse. Contre-épreuve : avec l'ancien style, le test tombe (2,07 sur le jaune).
  - **À 5 ou 6 questions, le tableau débordait sur un projecteur de 720 lignes.** Les cartes restaient sur deux colonnes, donc trois rangées : 130 px de trop avec des énoncés d'environ 135 caractères. Le test du 8 novembre ne vérifiait que N = 4. Trois colonnes à partir de 5 cartes, et un nouveau test à N = 6. La limite est écrite dans SPEC.md (SES-06) : des énoncés plus longs, ou un écran de 1024x768, peuvent encore défiler.
  - **En écrivant ce test, j'ai trouvé un défaut latent de la mesure.** Elle pouvait lire la page avant sa feuille de style : 11 075 px de « débordement », les formes SVG sans taille occupant toute la largeur. Le test SES-06 du 8 novembre avait le même défaut, sans qu'il se soit encore manifesté. La mesure attend désormais le chargement complet, et cinq passages sur cinq sont verts. Contre-épreuve : sans les trois colonnes, le test tombe pour la bonne raison (130 px en 1280x720).
  - **Les lettres du CSV après modification d'une question.** Elles désignent les propositions figées au lancement. Une fois la question modifiée, plus aucune page ne montre cet ordre. Le tableau ne le montrait de toute façon plus après la fin de la session, mais il le montrait pendant. La formulation de la spec, « comme dans la liste des questions », était fausse dans ce cas : elle est corrigée, et la question est posée au commanditaire (SPEC §5 bis).
  - **La liste blanche du test DER-03** admet désormais la mention des questions multiples. Sans cela, le test aurait dépendu de l'ordre des questions de ses données.
  - Écartés : la correspondance couleur → forme reste dans le gabarit, déjà discutée sous `/simplify`. La disparition du bandeau « Session démarrée » est voulue, depuis le 8 novembre, pour que 4 énoncés tiennent à l'écran : l'apparition du minuteur confirme le démarrage.
- **Pas de `/security-review`.** L'incrément ne touche ni aux entrées, ni à l'authentification, ni aux sessions, ni aux réglages : seulement à l'affichage.
- **`spec-auditor`, premier passage (commit aaaaeba) : une réserve bloquante.** Sa copie jetable était au bon commit, et le dépôt principal n'a pas bougé (même `HEAD`, `git status` vide, aucune copie oubliée). Il a fait 26 contre-épreuves et lancé `make verify`, vert dans sa copie.
  - **Bloquante : le test d'AFF-01 ne vérifiait pas les états JSON, alors qu'il l'annonçait.** `JsonResponse` écrit « É » en `\u00c9`, et les marqueurs du test sont tous accentués : la recherche dans le texte brut ne pouvait rien trouver. Énoncés envoyés au téléphone ou propositions envoyées au tableau par l'état JSON : le test passait. Ce test date de la session du 8 novembre, et je l'avais repris sans le mettre à l'épreuve. L'état est désormais décodé avant la recherche. J'ai refait les deux contre-épreuves, et les deux fuites sont détectées.
  - Non bloquantes, corrigées :
    - une mention « multiple » masquée à 1 px passait (le test exige désormais une hauteur lisible) ;
    - le contraste de la mention n'était vérifié que sur l'orange (une question multiple tombe désormais aussi sur le bleu, à texte blanc) ;
    - le test des formes a échoué une fois chez lui, pour la même cause que la mesure du débordement : une page lue avant sa feuille de style.

    Contre-épreuves refaites : toutes détectées, et cinq passages sur cinq verts pour le test des formes.
- **`spec-auditor`, second passage (commit fc9e47e) : une autre réserve bloquante, de la même famille.**
  - Ma correction décodait bien les états JSON, mais le test ne les lisait que pendant le déroulement. Une fuite en attente ou après la fin passait, alors que l'exigence dit « à aucun moment », et que les commentaires du test promettaient « nulle part » et « plus rien ».
  - J'ai corrigé le défaut que l'auditeur avait montré, sans chercher où d'autre la même recherche manquait : c'est ce que j'aurais dû faire au premier passage.
  - Les pages et les états JSON du tableau et des téléphones sont désormais lus à chaque phase. Contre-épreuves : énoncés envoyés au téléphone en attente, propositions envoyées au tableau après la fin, toutes deux détectées.
  - Non bloquante : en rendant multiple la question du bleu, j'avais retiré la mesure du bouton d'effacement sur la seule couleur à texte blanc. Une perte de couverture introduite en corrigeant une réserve : le même schéma qu'en I8. Un second groupe de six questions, toutes simples, la rétablit. Contre-épreuve : un bouton estompé sur le bleu seulement est détecté (contraste de 1,85).
- **`spec-auditor`, troisième passage (commit 9877daf) : aucune réserve bloquante.**
  - Onze contre-épreuves, toutes détectées : fuites JSON en attente, pendant le déroulement et après la fin, au tableau comme au téléphone ; bouton d'effacement estompé sur le bleu (inactif puis actif) et sur une couleur simple ; mentions illisibles sur le bleu et sur l'orange.
  - Cinq passages sur cinq verts pour les tests d'AFF-01 et des formes, et `make verify` vert dans sa copie.
  - Seule réserve, non bloquante : la ligne d'audit absente du REX. Mes ajouts n'étaient pas encore commités.
  - Il a limité ce passage aux points corrigés, les autres exigences ayant été couvertes par le premier (26 contre-épreuves).
  - Contrôle après chacun des trois passages : le dépôt principal n'a pas bougé (même `HEAD`, seules mes propres modifications du REX en cours, aucune copie oubliée).
  - Le dernier auditeur a écrit son script de mutation dans mon scratchpad, hors de sa copie : sans effet sur le dépôt, mais hors de ce qui lui était demandé.

Audit spec-auditor : 9877dafc970d7d06b801f72e4d417793ad5a5db0

### Ce qui a bien marché
- **Mesurer avant de proposer.** La palette a été choisie sur des chiffres et une image comparative, que le commanditaire a pu voir avant de trancher.
- **Vérifier une forme comme un œil la voit.** Le test d'AFF-03 compare les silhouettes des formes lues sur une capture, et non leur seul nom accessible. Il reconnaît aussi la forme du téléphone comme la plus proche de celle de la même couleur au tableau.
- **Vérifier le contraste de tout texte affiché,** et pas seulement celui des énoncés. C'est ainsi qu'ont été trouvés le texte gris et le bouton d'effacement illisibles sur le bleu.

### Ce que j'aurais dû savoir dès le départ
- **Une exigence déjà livrée peut revenir comme une demande nouvelle.** L'ordre propre à l'étudiant existait depuis I4. Il fallait le dire, puis expliquer ce qu'il garantit et ce qu'il ne peut pas garantir, plutôt que de le reconstruire.
- **Ajouter un élément visuel touche aux tests qui comptent ce qui est affiché.** Chercher ces tests avant de coder évite de les découvrir dans `make verify`.
- **Un test d'absence qui n'a jamais échoué ne prouve rien.** « Ce texte n'est pas dans la réponse » passe aussi quand la recherche ne peut pas le trouver : encodage, page pas encore chargée. Pour chaque vérification négative, faire au moins une fois la fuite exprès. C'est vrai aussi d'un test hérité d'une session précédente.
- **Une mesure de page se fait sur une page chargée.** Deux tests ont lu une page sans sa feuille de style, l'un par intermittence. Attendre la fin du chargement avant toute mesure de mise en page ou de couleur.

### Choix techniques et leur raison
- **Aucune nouvelle dépendance.**
- **Formes en SVG intégré** (`templates/live/shape.html`) plutôt qu'en caractères Unicode : leur rendu ne dépend pas des polices du téléphone ni du vidéoprojecteur. Elles prennent la couleur du texte, donc le blanc sur le bleu. Chacune porte un nom accessible.
- **La mention « multiple » vient du QCM figé** (`multiple`), comme l'énoncé : rien de nouveau n'est envoyé au tableau.

### Ce qui n'est garanti que par la consigne ou reste à vérifier
- **Les simulations ne remplacent pas un essai.** Le modèle de projecteur est grossier, et aucune personne daltonienne n'a vu l'écran. À vérifier en salle, avec le vrai projecteur.
- **Deux voisins peuvent voir une proposition au même endroit** (ETU-05) : c'est accepté, et la rotation (N = 4) le rend plus rare.
- **eduroam reste le risque principal** avant un premier cours (SPEC §5).

---

## I10 — Refonte visuelle : socle et tableau

### Objectif
Après I9, le commanditaire a demandé une refonte visuelle. J'ai proposé trois directions sur des maquettes statiques (tableau, téléphone, espace enseignant), avec les mêmes données fictives. Il a retenu la direction B, « Signalétique » : encre sur papier, bandeau noir, filets épais, police Atkinson Hyperlegible. Le découpage proposé a été validé : socle et tableau (I10), téléphone (I11). L'espace enseignant (I12) attend l'import AMC, qui en changera le contenu.

**Réponses du commanditaire, consignées dans SPEC.md :**
- formules, code et images : styles prêts seulement, contenu avec l'import AMC ;
- recherche et filtres de la banque : à revoir en I12, avec un filtre par QCM d'origine et un filtre « déjà posée à tel groupe » ;
- réseau lent : renvoi automatique, et une réponse arrivée après la fin de son créneau jamais affichée comme enregistrée (I11) ;
- « Questions 5–8 sur 24 », barres du temps restant, numéro à côté du nom : validés ;
- « Vos réponses ont été transmises » seulement si toutes ont été confirmées par le serveur (FIN-02, I11).

**Pas de plan mode.** La procédure le demande pour un choix de conception. Ici, le choix venait d'être fait par le commanditaire, sur les maquettes et le découpage, et il a demandé d'enchaîner I10 puis I11. Les choix qui restaient (graisse des énoncés, outil d'accessibilité) lui avaient été délégués ou relevaient de la technique.

### La graisse des énoncés
Le commanditaire m'a demandé de vérifier au tableau un énoncé d'environ 200 caractères, et d'abandonner le gras s'il l'alourdissait. J'ai fait deux captures du même tableau, 4 énoncés de 178 à 190 caractères, l'une en gras, l'autre en graisse normale, en 1920x1080 et en 1280x720.
- **À taille réelle**, le gras tasse les mots et noircit le paragraphe. La graisse normale garde des formes de lettres ouvertes et se lit mieux.
- **En simulation de projecteur vu du fond de la salle** (image réduite au quart, légèrement floutée, voile de lumière ambiante), la graisse normale perd un peu de corps sur le vert et le bleu ciel, sans devenir illisible. Le gras y reste plus dense, mais ses lettres commencent à se confondre.
- **Décision :** graisse normale pour les énoncés, gras pour les numéros, les étiquettes et les titres. Le gras ne tient plus dans les deux cas. Si l'essai en salle montre un texte trop fin, la police, à graisse variable, permet une graisse intermédiaire (500) sans autre fichier : c'est un réglage d'une ligne, à décider sur place.
- Les énoncés ont ensuite été agrandis selon le nombre de questions affichées : un énoncé de 200 caractères (135 à 5 et 6) occupe environ les deux tiers de sa carte, et il reste de la place pour un énoncé plus long.

### Tests d'acceptation
Écrits avant le code et lancés aussitôt : 6 échecs sur 10, chacun pour la raison attendue.
- **VIS-01** : police non chargée, texte en `system-ui`.
- **VIS-02** : pas de bandeau ; à 5 et 6 questions, 18 px de trop en 1280x720.
- **VIS-03** : pas de zone « Rejoindre la session ».
- **ACC-01** : focus de 1 px, celui du navigateur.

Les cas de 1 à 4 questions du test de VIS-02 passaient déjà, taille des énoncés comprise : ce sont des garde-fous, pas des tests rouges. axe-core ne relevait rien sur l'accueil avant la refonte. C'est le contrôle du clavier qui a fait échouer ACC-01 en premier.

### Problèmes rencontrés
- **La suite existante a trouvé deux régressions que mes tests d'I10 ne voyaient pas.**
  - En passant dans le bandeau, hors de `<main>`, le formulaire « +10 s » échappait à `board.js`, qui ne mettait plus à jour son créneau. Au second créneau d'un même groupe, le clic visait le premier et n'ajoutait rien (TPS-01, I5).
  - Le lien « Gérer les connectés » n'était plus affiché qu'en attente, alors que SES-04 l'ouvre depuis le tableau à toute phase (I4).
- **Le bandeau sorti de `<main>` échappait aussi au test de DER-03.** Sa liste blanche ne parcourait que `<main>`. Le minuteur, la position et le code n'étaient donc plus contrôlés, et le test passait. Je l'ai vu en relisant ce test, à cause d'un autre constat de `/simplify`. Il parcourt désormais toute la page. Il a aussitôt attrapé un défaut : un commentaire de gabarit sur deux lignes, en `{# … #}`, s'affichait tel quel, Django ne reconnaissant cette syntaxe que sur une ligne. Il est passé en `{% comment %}`.
- **Ma mesure de la barre lisait 0.** La barre des connectés est placée à une position fractionnaire (x = 25,9 px) : la capture déborde d'un pixel de fond de chaque côté. La mesure écarte désormais ces deux pixels. C'était un défaut du test, pas de la page.
- **Des tests existants ont changé avec l'interface.** Minuteur en « 0:18 » au lieu de « 18 s », décompte « 0 / 3 » sous le titre « Connectés », adresse seule dans son élément, liste des sessions atteinte par le logo depuis le tableau, qui n'a plus la navigation de l'enseignant. Chaque aide a été adaptée sans affaiblir ce qu'elle vérifie. Le test de CLA-01 vérifie même l'adresse plus strictement : texte exact au lieu d'un « contient ».
- **Une précision de SES-06 est devenue fausse.** 3 questions s'affichent désormais sur trois colonnes, et non sur deux. SES-06 le dit maintenant.
- **pre-commit a modifié les licences de la police** (espaces en fin de ligne). Je les ai restaurées telles que publiées, et les fichiers tiers (polices, axe-core) sont exclus de ces contrôles. Le commit avait échoué sans rien enregistrer, grâce à l'enchaînement par `&&`.
- **Mon script de capture a d'abord été écrit dans `tests/e2e/`**, pour profiter des fixtures. Je l'ai déplacé dans le scratchpad avant le premier commit du code, et `git status` le confirmait.

### Ce que les revues ont trouvé
- **`/simplify`, quatre relecteurs : rien de bloquant.**
  - Corrigé :
    - la durée d'un créneau est calculée une seule fois (`Schedule.lengths`), pour les échéances comme pour la barre ;
    - le suivi du direct est rattaché à `<body>`, et non plus à `<main>` : le minuteur, la barre et « +10 s » du bandeau restent dans son périmètre, sans recherche dans toute la page ;
    - le bandeau est construit par blocs dans la base, plutôt que recopié par le tableau, et le code de session est découpé dans un seul gabarit ;
    - les deux barres partagent leurs règles (variables `--track` et `--value`), et la palette est déclarée une seule fois ;
    - le minuteur n'écrit plus qu'une fois par seconde, et la liste des connectés n'est reconstruite que si elle a changé ;
    - côté tests : parcours des textes visibles et nom d'un élément mis en commun, tailles d'écran en une constante avec un seul passage, contrôle groupé des 40 noms ;
    - le test d'I9 « 6 questions tiennent » est retiré : le test paramétré d'I10 le contient, et porte aussi SES-06.
  - Écarté :
    - tailles des énoncés par requêtes de conteneur plutôt que par N : les tailles actuelles ont été choisies à l'œil, sur captures ;
    - deux aides distinctes pour la liste des sessions : aucune page n'a les deux liens ;
    - barre animée en CSS plutôt que recalée tous les quarts de seconde : le coût est négligeable sur le PC.
- **`/code-review`, six constats, aucun bug bloquant.**
  - **Un trou de test**, le plus utile : rien ne vérifiait que la barre du temps se recale sur la durée d'un nouveau créneau sans recharger la page (même groupe, après un « +10 s » au précédent). Le test de VIS-02 passait par des rechargements à chaque fois. Le cas est ajouté. Contre-épreuve : sans la ligne qui recale la barre, le test tombe, avec une barre à 0,55 au lieu de 0,83.
  - **L'inventaire des dépendances de CLAUDE.md (règle 5) était faux** : il ne citait ni axe-core ni les polices. Il est complété, et leur besoin est écrit ci-dessous.
  - **Le tableau n'a plus la navigation de l'enseignant ni le bouton de déconnexion.** C'était voulu (la maquette validée n'en a pas, et la page est projetée), mais rien ne l'écrivait : c'est désormais une précision de VIS-02. Le logo ramène à la liste des sessions.
  - **L'aide `open_sessions` acceptait deux liens différents.** Elle est séparée en deux : la navigation de l'enseignant, et `leave_board` pour le logo du tableau. Chaque test dit ainsi quel chemin il emprunte.
  - **La docstring de `_position_label`** décrivait un libellé faux ; elle est corrigée.
  - **`slot_ms` partait aussi vers les téléphones**, qui n'ont pas encore de barre : il est réservé au tableau jusqu'à I11.
- **Pas de `/security-review`.** L'incrément ne touche ni aux entrées, ni à l'authentification, ni aux sessions, ni aux réglages (la CSP est inchangée et couvre la police, servie par l'application).

- **`spec-auditor`, premier passage (commit 543399b) : deux réserves bloquantes, toutes deux sur VIS-02.** Sa copie jetable était au bon commit. Il a fait 22 contre-épreuves, et le dépôt principal n'a pas bougé (même `HEAD`, `git status` vide, aucune copie oubliée).
  - **Une barre du temps qui ignore le temps ajouté passait le test.** Ma mesure recommençait jusqu'à entrer dans la tolérance. Or la barre baisse d'elle-même : une barre trop pleine finissait toujours par y descendre. L'auditeur l'a prouvé en instrumentant la mesure : 0,79 pour 0,625 attendu, acceptée à 0,72 après 2,4 s.
    - La barre est désormais comparée au minuteur lu juste avant et juste après la capture. Comme les deux baissent ensemble, attendre ne rapproche plus une barre fausse de la valeur juste.
    - Contre-épreuve refaite : la barre est lue à 0,70 pour 22 s restantes sur 40, et le test tombe.
    - J'avais fait la même erreur de raisonnement que pour les tests d'absence d'I9 : une tolérance avec de nouvelles tentatives, sur une grandeur qui change d'elle-même, finit par tout accepter.
  - **Aucun test n'affichait 60 s ou plus.** Un minuteur qui écrirait « 0:75 » passait les 499 tests. Un test à créneaux de 90 s vérifie maintenant « 1:30 » puis « 0:59 », au tableau comme sur un téléphone. Contre-épreuve refaite : « 0:89 » est refusé.
  - Non bloquantes, corrigées, chacune avec sa contre-épreuve refaite et détectée :
    - la taille du code de session (« en grands chiffres » : au moins 8 % de la hauteur de l'écran, désormais écrit dans VIS-03) ;
    - l'absence de navigation et de déconnexion au tableau, en attente comme une fois terminé ;
    - « Gérer les connectés » une fois la session terminée.
  - Non bloquantes, corrigées sans contre-épreuve : la mesure d'une barre lit désormais la couleur de sa valeur, et une barre vide mesure 0 au lieu de 1. La position de la barre, sous le bandeau, est vérifiée.
  - Non bloquante, laissée : les pages d'erreur 400 et 500 ne passent pas le contrôle d'ACC-01. Un navigateur ne peut pas forger l'en-tête `Host` qui déclencherait la 400, et aucune adresse ne provoque une erreur 500. Elles partagent la base et les styles des pages 404 et 403, qui sont contrôlées.
- **`spec-auditor`, second passage (commit 04226a0) : une réserve bloquante.** Ses seize contre-épreuves confirment les corrections : barre sans le temps ajouté, trop pleine, en avance ou vide, minuteur sans les minutes, code en petits chiffres, navigation au tableau, lien absent à la fin. Toutes détectées sauf deux.
  - **Bloquante : rien ne mesurait la barre dans le dernier tiers du créneau.** Toutes mes mesures tombaient entre 0,4 et 0,9. Une barre qui ne descend jamais sous 40 %, ou qui reste bloquée à 15 % jusqu'à l'échéance, passait les 68 tests de bout en bout, alors que VIS-02 dit « elle se vide jusqu'à l'échéance ».
    - Une mesure à 10 s de la fin d'un créneau de 90 s est ajoutée, avec dix secondes de marge avant le créneau suivant.
    - Contre-épreuves refaites : barre lue à 0,40 pour 7 s sur 90, puis à 0,15, toutes deux refusées.
    - Leçon : une mesure doit couvrir toute l'étendue de ce que l'exigence promet, et en particulier ses extrémités.
  - Non bloquantes, laissées :
    - la tolérance de la barre, d'environ 1,6 s sur un créneau de 30 s, acceptable pour une barre vue de loin ;
    - la taille du code de session, lue sur la police calculée et non sur la hauteur dessinée, qu'une transformation CSS tromperait (cas artificiel).
- **`spec-auditor`, troisième passage (commit eea9965) : aucune réserve bloquante.**
  - Sept contre-épreuves sur la fin du créneau : planchers à 40 %, 25 % et 15 %, barre pleine puis vide à 10 s de la fin, barre vidée trop tôt.
  - Toutes sont détectées, sauf un plancher de 12 % : non bloquant, peu visible de loin. Une mesure plus près de l'échéance, sur un créneau court, le ramènerait à 5 % environ, au prix d'une marge plus étroite avant le créneau suivant.
  - Test stable : trois passages sur trois, et le fichier entier deux fois sur deux.
  - Contrôle après chacun des trois passages : le dépôt principal n'a pas bougé (même `HEAD`, seules mes modifications en cours, aucune copie oubliée).

Audit spec-auditor : eea9965f9ba485a5f6dd8d8079e6bee66ea945de

### Choix techniques et leur raison
- **Atkinson Hyperlegible Next, servie par l'application** (`static/fonts/`, licence OFL, environ 80 ko au total). Besoin : une police qui distingue les caractères proches (I, l, 1 ; O, 0) pour le code de session et les numéros, et qui s'affiche sans Internet, la salle n'en ayant pas forcément. La CSP, qui n'autorise que l'application elle-même, l'imposait de toute façon. C'est la version à graisse variable : un seul fichier par jeu de caractères, et une graisse intermédiaire possible sans autre fichier. Le jeu latin étendu et la version à chasse fixe (pour le code, à venir) ne sont téléchargés que si une page en a besoin.
- **axe-core 4.14.0, livré dans `tests/e2e/vendor/`** (MPL-2.0), en test seulement. Besoin : le contrôle automatique d'accessibilité promis avec les maquettes (ACC-01). Le paquet Python qui l'embarque n'était plus maintenu et contenait une ancienne version : le fichier publié sur npm, vérifié contre l'empreinte de l'archive officielle, est plus sûr et ne dépend pas du réseau en CI. Il est évalué par Playwright, hors de la page, et la CSP de l'application reste donc en place pendant le contrôle.
- **Le suivi du direct sur `<body>`.** Le bandeau, hors de `<main>`, porte le minuteur, la barre et « +10 s ». Rattacher le suivi au `<body>` les garde dans son périmètre ; chercher dans tout le document aurait été une rustine.
- **Une barre en `<progress>`.** Elle s'affiche sans JavaScript à la bonne valeur, et ne demande aucun style inline, que la CSP refuserait.
- **Le logo en CSS** (quatre carrés en dégradé conique). Une image ou un SVG aurait été compté comme image par le test de SES-05, qui vérifie qu'aucun QR code ne reste au tableau.
- **Tailles du tableau en `em`, sur 1,5 % de la hauteur de l'écran** : une seule mise en page pour 1080 et 720 lignes.

### Ce qui a bien marché
- **Montrer avant de coder.** Les trois directions, sur les mêmes écrans et les mêmes données, ont permis au commanditaire de choisir et de répondre aux questions en une fois.
- **Mesurer la barre sur une capture**, comme un œil la voit, plutôt que de lire sa valeur : la mesure vaut quel que soit le moyen de dessiner la barre.
- **La suite existante comme filet.** Les deux régressions de cet incrément ont été trouvées par des tests d'I4 et d'I5, et non par les nouveaux.

### Ce que j'aurais dû savoir dès le départ
- **Déplacer un élément change ce que les scripts et les tests trouvent.** Sortir le minuteur et « +10 s » de `<main>` a cassé `board.js` et fait sortir le bandeau du test de DER-03. Avant de déplacer un élément, chercher qui le trouve par son conteneur : scripts, tests, et surtout tests d'absence (liste blanche), qui passent alors sans rien dire.
- **`{# … #}` ne vaut que sur une ligne** dans un gabarit Django. Sur deux lignes, le commentaire s'affiche.

### Ce qui n'est garanti que par la consigne ou reste à vérifier
- **La graisse normale au vidéoprojecteur.** Ma simulation suggère une petite perte de corps sur le vert et le bleu ciel. À vérifier en salle ; une graisse de 500 se règle en une ligne.
- **Un contrôle automatique ne trouve qu'une partie des défauts d'accessibilité.** Aucun essai n'a été fait avec un lecteur d'écran.
- **Le tableau n'est vérifié qu'en 16:9** (1920x1080 et 1280x720). Un projecteur en 4:3 (1024x768) peut faire défiler les énoncés longs, comme le prévoit SES-06.

## I11 — Refonte du téléphone et réseau lent

### Objectif
Seconde partie de la refonte visuelle (direction « Signalétique ») : le téléphone dans tous ses états (VIS-04) et son accessibilité (ACC-02). S'y ajoutent les réponses du commanditaire sur le réseau lent (ETU-10), la perte de connexion (ETU-11) et le message de fin (FIN-02, précisée). Les exigences étaient déjà rédigées et validées dans SPEC.md, non commitées, au début de la session.

**Question posée avant d'écrire les tests.** ETU-07 veut qu'un téléphone rechargé réaffiche « la réponse enregistrée » ; ETU-10, qu'il renvoie seul la dernière réponse et garde la trace de ses envois après un rechargement. Les deux se contredisent quand un envoi est en attente au moment du rechargement. Réponse : le téléphone réaffiche ce dernier choix et continue de l'envoyer. Elle est consignée sous ETU-10 et dans le journal des décisions.

**Pas de plan mode.** Le fonctionnel était tranché par le commanditaire. Le seul choix de conception (comment le téléphone apprend ce que le serveur a enregistré) est technique : il est décrit ci-dessous.

### Tests d'acceptation
Écrits avant le code et lancés aussitôt : 13 échecs sur 13, chacun pour la raison attendue.
- « Envoi en cours… » absent (7 tests d'ETU-10, de FIN-02 et d'ACC-02).
- Aucune alerte « Connexion perdue » (ETU-11, et l'écran de perte de connexion de VIS-04).
- Pas de bandeau sur le téléphone (VIS-04, et le message de fin qui le suppose).
- Le test de FIN-02 d'I8, précisé : pas de phrase « Vos réponses ont été transmises ».

Avant tout code, ACC-02 passait sur tous les états existants du téléphone ; il n'échouait qu'à l'état « envoi », qui n'existait pas. C'est un garde-fou plus qu'un test rouge.

Le réseau du téléphone est simulé par Playwright, en trois modes vérifiés d'abord sur un script jetable :
- requête coupée ;
- requête retenue puis relâchée plus tard depuis le test ;
- requête qui atteint le serveur, mais dont la réponse se perd.

`set_offline` coupe tout le réseau du navigateur. Piège rencontré dans ce script jetable : un `page.evaluate` qui renvoie la promesse d'un `fetch` retenu attend sa fin, et bloque le test. Le script a tourné deux minutes avant que je l'arrête.

### Problèmes rencontrés
- **Trois régressions trouvées par la suite existante, une seule cause.** Le téléphone en déroulement n'affichait plus « Vous êtes … ». Or un étudiant arrivé après le démarrage (ETU-08) arrive directement sur cet écran, et c'est sa seule confirmation d'identité (ETU-01). Trois tests d'I4 et d'I6 sont tombés. Le pied porte désormais « Vous êtes NOM · N° numéro », ce qui répond aussi à VIS-04. Comme en I10, ce sont les anciens tests, et non les nouveaux, qui ont trouvé la régression.
- **La barre du temps disparaissait sur la couleur 1** (contrôle visuel des captures). Le jaune de la barre est celui de la couleur 1 : sur ce fond, on ne voyait que la partie déjà écoulée. Le test de VIS-04 mesurait la barre seule, sans son entourage. Un filet d'encre la sépare désormais du fond, et un test mesure ce contraste ; il échoue sans le filet. Ma première version de cette mesure était fausse : elle cherchait le filet « après la dernière ligne jaune », qui était le fond de la page, jaune lui aussi.
- **Le test de FIN-02 d'I8 a dû changer.** Il exigeait que le téléphone n'affiche que « Session terminée. ». FIN-02, précisée en I11, ajoute la phrase sur la transmission, et le bandeau ajoute « QCM Live » et le code. Le test vérifie toujours l'absence de QR code, de réponses et de note, et le texte exact de la page.
- **Avertissements à la fermeture du navigateur.** Des interceptions réseau encore actives à la fin d'un test produisaient des « coroutine never awaited ». Chaque test rétablit désormais le réseau du téléphone en attendant la fin des interceptions en cours, et le fichier passe avec ces avertissements traités en erreurs.
- **Deux commandes refusées par les garde-fous** (`guard_bash.py`) : un pipe après `pyright`, puis un `;` après `pytest`. Les deux ont été refaites avec `pipefail` et `&&`, et aucun code de retour n'a été perdu. La première, refusée en entier, emportait une correction de lint que j'ai crue appliquée, d'où un second passage de ruff qui échouait sur les mêmes lignes.
- **Un remplacement global a cassé la fixture `networks`** : `Network(` remplacé par `networks(` jusque dans la fixture elle-même, qui s'appelait donc elle-même. Neuf tests en échec, vus aussitôt et corrigés avant le commit.

### Ce que les revues ont trouvé
- **Contrôle visuel** (captures Pixel 7 et 360 px de chaque état) : la barre sur la couleur 1 (ci-dessus), « N° » séparé du numéro en fin de ligne, et le message des réponses non transmises, peu visible pour un avertissement. Les trois sont corrigés.
- **`/simplify`, quatre relecteurs, rien de bloquant.**
  - Corrigé :
    - une seule fonction de requête dans `poll.js` (délai d'abandon, contact noté) ;
    - l'échéance du compte à rebours, que le téléphone lit au lieu d'en tenir une copie ;
    - les messages communs avec le serveur, lus dans la page au lieu d'être recopiés en JavaScript ;
    - la question au serveur, qui cesse sur un refus au lieu de réessayer sans fin ;
    - l'avertissement de fin, sur la classe `.error` existante ;
    - les règles CSS et la classe mortes, retirées ;
    - côté tests : les constantes de `live.views` et `background()` réutilisées, les groupes de boutons radio rattachés à l'élément formulaire.
  - Écarté :
    - fusionner `wait_recorded` avec `wait_answer` : le premier compare toutes les réponses par leur texte, le second une question par ses indices ;
    - éviter la seconde question au serveur, à l'écran suivant, quand l'échéance l'a déjà posée : une requête de plus, seulement pour un téléphone qui a perdu une réponse ;
    - remplacer les attentes fixes du test d'ETU-11 : elles laissent au téléphone le temps d'interroger le serveur avant la coupure.
- **`/code-review`, neuf constats, huit corrigés dans le code et un dans la documentation.**
  - **Le plus sérieux** : au rechargement, un navigateur qui restaure l'état du formulaire (Firefox) aurait fait passer pour reçue une réponse jamais envoyée. C'est la fausse confirmation qu'ETU-10 interdit. Le téléphone compare désormais sa trace à ce que la page cochait à son arrivée (`defaultChecked`), et le formulaire n'est plus restauré (`autocomplete="off"`). Pas de test : Chromium ne restaure pas ce formulaire, et la suite ne tourne que sous Chromium.
  - Un choix fait après l'échéance du téléphone restait en « Envoi en cours… », ou effaçait de la trace une réponse confirmée. Les propositions se verrouillent désormais à l'échéance, et se déverrouillent si le serveur annonce du temps ajouté.
  - Avec le stockage refusé, la réponse perdue n'était pas signalée sur le moment. La trace vit désormais en mémoire et se recopie dans le stockage.
  - Une réponse choisie puis effacée valait « Vos réponses ont été transmises ». Ce n'est pas une réponse : le téléphone n'affiche plus que « Session terminée. ».
  - Sans `AbortSignal.timeout` (iOS 15), une requête perdue bloquait tous les envois suivants. La requête est désormais abandonnée par un minuteur.
  - Corrigés aussi :
    - le message après la question au serveur, tiré de la réponse effectivement confirmée ;
    - les pertes déjà signalées, qui ne sont plus redemandées au serveur ;
    - la proposition choisie, marquée par une classe plutôt que par `:has()`, absent des navigateurs anciens.
  - CLAUDE.md décrivait encore l'ancien téléphone : corrigé.
  - Trois tests ajoutés (verrouillage, stockage refusé, réponse effacée), chacun en échec sur le code d'avant ces corrections, pour la raison attendue.
- **`/security-review` : aucun constat.** La nouvelle route ne lit l'identité que dans la session Django, et ne renvoie que des indices de propositions. Les textes sont insérés avec `textContent`, et la CSP est inchangée.
- **`spec-auditor`, premier passage (commit 231fbf0) : trois réserves bloquantes, toutes dans les tests.** Aucune erreur dans le code, mais 6 mutations sur 21 survivaient (dont 2 équivalentes). Copie jetable au bon commit ; le dépôt principal n'a pas bougé (`git status` vide, aucune copie oubliée).
  - **La question au serveur.** Elle est posée à trois moments : à l'échéance, à l'écran suivant, à la fin. Chacune pouvait être retirée seule sans qu'un test échoue. Sans la première, un étudiant dont la réponse était bien arrivée lisait « Temps écoulé : réponse non enregistrée ». Le test de la confirmation perdue lit désormais l'écran à l'échéance. Un nouveau test coupe tout le réseau avant l'échéance, pour que l'écran suivant, puis la fin, aient seuls à demander.
  - **La proposition choisie restait noire après un changement de réponse** : le test ne regardait que le premier choix. Il vérifie désormais un changement et un effacement.
  - **Les 48 px des propositions n'étaient mesurés qu'avec des textes de plusieurs lignes.** Ils le sont aussi sur les six téléphones du test d'accessibilité, aux propositions courtes.
  - Non bloquante, corrigée : un délai de 4 s pour « Connexion perdue » passait. Le délai est désormais mesuré dans la page, depuis la dernière réponse du serveur : entre 3 s et 3,4 s.
  - Non bloquantes, laissées :
    - la correspondance entre créneau et question de la nouvelle route n'est vérifiée qu'en intégration, avec rotation ;
    - aucun test ne couvre un envoi qui doit reprendre quand du temps est ajouté après l'échéance du téléphone (cas rare : il faut que le téléphone ait perdu l'état du direct au moment du « +10 s »).
  - **Mon premier renforcement était faux.** Le test coupait l'état du direct juste après avoir avancé le déroulement, avant que le téléphone ait recalé son compte à rebours, qui croyait donc avoir encore 28 s. Une sonde a montré que le code faisait ce qu'il fallait ; le test attend désormais le recalage.
  - Contre-épreuves refaites après correction : les six mutations survivantes sont toutes détectées, chacune pour la raison attendue.
- **`spec-auditor`, second passage (commit 2a4df6d) : une réserve bloquante.** Les six mutations du premier passage sont détectées ; 22 nouvelles l'ont été aussi, sauf six. Fichier stable (trois passages complets). Copie au bon commit ; le dépôt principal n'a pas bougé.
  - **Bloquante : la confirmation d'une réponse remplacée** pouvait valoir pour la suivante sans qu'un test échoue. L'étudiant passe de « Paris » à « Lyon » pendant un envoi lent ; « Paris » arrive, « Lyon » jamais. Le code était juste, mais une ligne déplacée aurait fait afficher « transmises » à la fin. Le test de l'envoi lent relâchait les deux envois, et ne pouvait pas le voir. Un test retient désormais « Lyon » jusqu'à l'échéance.
  - Non bloquantes, corrigées :
    - le bandeau rouge de « Connexion perdue » pouvait rester visible, vide (le test cherchait son texte) ;
    - l'alerte « toujours à l'écran » était vérifiée sur une page trop courte pour défiler ;
    - une clé de trace commune à toutes les sessions passait : un même téléphone peut servir deux fois dans la journée ;
    - le grand numéro de couleur n'était pas vérifié ;
    - l'état verrouillé à l'échéance n'était pas contrôlé par ACC-02.
  - Non bloquant, laissé : la perte d'une réponse peut être rappelée sur les écrans suivants, ce que la spec n'interdit pas.
  - **Un test en échec bloquait au démontage.** Sous la mutation, le nouveau test échouait bien, puis la fixture attendait sans fin. Le réseau du premier `Network` attendait des requêtes retenues par le second. La fixture relâche désormais toutes les requêtes retenues avant de couper les interceptions. Le défaut aurait figé la CI au premier vrai échec de ce test.
  - **Deux fois, j'ai rendu la main pendant mes contre-épreuves en arrière-plan.** Le hook Stop a lancé `make check` sur la même base de test, alors qu'un `pytest` tournait sur du code muté. Un résultat est tombé sur « attempt to write a readonly database » ; un autre venait d'une exécution que j'avais arrêtée. Les deux ont été refaits seuls, au premier plan. CLAUDE.md l'interdisait déjà pour `make verify` : la règle vaut pour tout `pytest` lancé en arrière-plan dans le dépôt.
  - Contre-épreuves refaites après correction : toutes détectées, chacune pour la raison attendue. Le fichier passe deux fois de suite.
- **`spec-auditor`, troisième passage (commit 0d8ab6a) : aucune réserve bloquante.**
  - Toutes les mutations des passages précédents sont détectées, chacune pour la raison attendue, ainsi que quatre nouvelles : un renvoi après l'échéance, une barre d'envoi qui ne colle plus, une réponse changée qui garde l'ancienne confirmation, un état verrouillé estompé.
  - L'auditeur a provoqué un échec à trois endroits où des requêtes sont retenues : le démontage ne bloque plus.
  - Fichier stable : deux passages complets, plus un troisième. Copie au bon commit ; le dépôt principal n'a pas bougé.
  - Non bloquantes, laissées :
    - la question au serveur n'est vérifiée de bout en bout que pour un téléphone de rang 0, avec une question à la fois, où créneau et question coïncident ; la rotation n'est vérifiée qu'en intégration ;
    - rien ne vérifie que la perte d'une réponse n'est signalée qu'une fois : la spec dit « dès l'écran suivant », sans plus ;
    - un envoi qui doit reprendre quand du temps est ajouté après l'échéance du téléphone.

Audit spec-auditor : 0d8ab6a60a5fdeffb87e9d56615ac2b350040408

**Langue, constaté après coup (section M) :** 71 de mes 75 messages de cet incrément étaient en anglais, malgré la règle 7. Cette section n'en disait rien.

### Choix techniques et leur raison
- **Le téléphone tient une trace de ses envois, le serveur reste l'arbitre.** Le téléphone ne peut pas savoir seul si une réponse sans confirmation est arrivée : la requête a pu atteindre le serveur et seule la réponse se perdre. Plutôt que de deviner, il compare sa trace à ce que le serveur a enregistré, par une route qui ne donne que des indices de propositions par créneau. C'est elle qui décide à l'échéance, à l'écran suivant et à la fin. Aucune nouvelle table, aucun nouvel état côté serveur : `Answer` suffisait.
- **Une réponse par créneau, la dernière donnée.** La trace ne garde, par créneau, que la dernière réponse et sa confirmation. Une réponse confirmée puis remplacée par une autre qui ne passe pas compte comme non transmise, puisque ce n'est pas celle que l'étudiant voulait.
- **Un seul envoi à la fois.** Chaque envoi part avec l'état du formulaire au départ, et le suivant ne part qu'à son retour. La dernière réponse arrive donc toujours en dernier, même sur un réseau lent, sans numéro de version ni horodatage côté serveur.
- **Verrouillage à l'échéance du téléphone.** La fin du créneau est connue du téléphone par son compte à rebours, recalé chaque seconde sur le serveur. Au-delà, plus aucun choix ne part. Le serveur refuse de toute façon (ETU-07), mais le téléphone peut ainsi dire « non enregistrée » sans réseau.
- **« Connexion perdue » mesure les réponses du serveur, pas les erreurs.** Une requête suspendue sans erreur, sur un réseau qui ne répond plus, compte comme une perte de contact. Toute réponse du serveur, même un refus, rétablit le contact.
- **Aucune dépendance nouvelle.** Le stockage local et `AbortController` sont dans tous les navigateurs visés.

### Ce qui a bien marché
- **Essayer l'outil de test avant d'écrire les tests.** Un script jetable a confirmé que Playwright savait retenir une requête, puis la relâcher, ou la laisser atteindre le serveur sans réponse. Sans cela, les tests d'ETU-10 n'auraient pas pu reproduire le cas « reçue mais non confirmée ».
- **Les captures d'écran, lues une à une.** Elles ont trouvé la barre invisible sur la couleur 1, qu'aucun test ne voyait.
- **Une contre-épreuve pour chaque test ajouté après les revues** : chacun a été lancé sur le code d'avant la correction, et a échoué pour la raison attendue.

### Ce que j'aurais dû savoir dès le départ
- **Une mesure d'élément ne dit rien de son entourage.** La barre était juste, mais invisible sur un fond de sa couleur. Tester un repère visuel, c'est aussi tester son contraste avec ce qui l'entoure.
- **Le navigateur peut restaurer un formulaire au rechargement.** Toute logique qui lit l'état des cases au chargement doit lire ce que le serveur a envoyé (`defaultChecked`), pas ce que le navigateur a remis.
- **Chercher qui dépend d'un texte avant de le déplacer.** « Vous êtes … » servait aussi de confirmation au retardataire : déjà la leçon d'I10, pour un élément déplacé.

### Ce qui n'est garanti que par la consigne ou reste à vérifier
- **Les tests ne tournent que sous Chromium.** La restauration du formulaire par Firefox, iOS 15 sans `AbortSignal.timeout` et les navigateurs sans `:has()` sont traités dans le code, mais aucun test ne les reproduit.
- **Le réseau est simulé par Playwright.** Coupures, requêtes retenues et réponses perdues sont réalistes, mais ce ne sont pas les pertes d'un Wi-Fi d'école chargé. L'essai en classe sur eduroam reste le risque principal (SPEC §5).
- **La trace des envois dépend du navigateur de l'étudiant.** Stockage effacé, navigation privée refermée ou autre navigateur : le téléphone n'affirme rien à la fin. C'est voulu (FIN-02), mais il ne peut pas non plus avertir.
- **Le verrouillage suit l'horloge du téléphone, recalée sur le serveur.** Un choix fait dans la dernière fraction de seconde peut être verrouillé alors que le serveur l'aurait accepté. Il est alors signalé comme non enregistré, jamais l'inverse.
- **Accessibilité : contrôle automatique seulement.** Aucun essai avec un lecteur d'écran sur téléphone (VoiceOver, TalkBack).

## M — Méthode : audit borné, pytest sans collision, langue surveillée

### Objectif
Avant l'import AMC, le commanditaire a demandé trois ajustements de méthode, pour tenir les délais et la consommation :
1. au plus deux passages de `spec-auditor` par incrément ;
2. un mécanisme, et non plus une consigne, contre la collision entre le hook Stop et un pytest déjà lancé ;
3. consigner la dérive vers l'anglais d'I11 et trouver plus fiable qu'une consigne.

Aucune exigence de SPEC.md ne change, et `[tool.qcm] increment` reste à 11 : on vérifie avec `make accept INC=11`. Branche `inc/m-methode`, tag `inc-m`, comme R.

### Problèmes constatés
- **La dérive de langue d'I11 n'était pas consignée.** Sur 75 messages du fil principal d'I11, 71 étaient en anglais, sans compactage de contexte.
  - Le premier message en anglais arrive 20 s après le chargement du skill `increment`, alors que le commanditaire écrivait en français.
  - Quelques messages repassent en français au moment de poser la question sur ETU-10, puis tout est en anglais à partir de 9 h 49, une demi-heure avant `/simplify`.
  - La cause avancée jusque-là (les prompts anglais des skills de revue) ne suffit donc pas. Je ne connais pas la vraie cause. La règle de CLAUDE.md, présente depuis I0, n'a rien empêché.
- **Collision entre deux pytest.** Avant M, tous les pytest du dépôt partageaient `.test-db.sqlite3`. Je l'ai reproduite avant de corriger : un E2E d'I5, puis `make test` lancé 12 s plus tard, donnent 1 échec et 13 erreurs (32 « no such table: live_session », 14 « readonly database »). Deux `make test` simultanés passent par chance : leurs connexions déjà ouvertes gardent l'ancien fichier.

### Choix et leur raison
- **Une base de test par processus** (`.test-db-<pid>.sqlite3`). C'est le seul de ces mécanismes qui empêche vraiment la collision, quel que soit celui qui lance le second pytest : le hook, moi, un agent. Au démarrage, pytest supprime les bases dont le processus n'existe plus (pytest tué). J'ai préféré un fichier par pid à un fichier temporaire : les tests du mode classe lisent le nom dans les réglages pour le passer au serveur lancé à part, et ce nom ne change pas.
- **Le hook Stop ne lance pas `make check` pendant un pytest du projet** (worktrees compris, lu dans `/proc`). Même sans collision de base, un second pytest prend du processeur aux E2E à faible marge de temps, et vérifierait du code en cours de mutation. Le contrôle se fait à l'arrêt suivant.
- **Langue : un réglage et un hook.**
  - `"language": "french"` dans `.claude/settings.json` place la consigne dans le prompt système, et non plus seulement dans CLAUDE.md. Cela reste une consigne.
  - `.claude/hooks/language.py` compte des mots-outils anglais et français, hors code. En hook PostToolUse, il m'avertit en cours de tour, dès le premier appel d'outil qui suit un message anglais : la dérive d'I11 a commencé au milieu d'un tour. Dans le hook Stop, il renvoie au travail un tour qui contient un message anglais, une fois par arrêt.
  - Je l'ai étalonné sur les journaux de toutes les sessions. Les quatre sessions tenues en français que j'ai rejouées, dont celle d'I10, ne déclenchent rien. Sur I11, il aurait averti 58 fois, une fois par message anglais suivi d'un appel, et renvoyé au travail 17 tours sur 23. Sur la session d'I0 à I4, 86 avertissements et 47 tours sur 78. Restent non détectés : des messages très courts (« Now README: »).
- **Audit borné.** Premier passage complet ; second passage facultatif, limité aux réserves bloquantes du premier, dont je transmets la liste ; ensuite, ce qui reste va dans le REX, sous « Réserves ouvertes ». Exception : une réserve qui touche la justesse des notes ou la séparation énoncé/propositions (AFF-01) reste bloquante. Je la corrige, puis je refais moi-même les contre-épreuves de l'auditeur, sans troisième passage. *C'est mon interprétation de la demande, à confirmer par le commanditaire.*

### Ce qui est garanti, et ce qui ne l'est pas
- **Imposé par un mécanisme :** deux pytest n'ont plus la même base de test. Un test d'intégration lance deux pytest à la fois sur un test qui écrit en base, et la démonstration réelle passe : le même E2E d'I5 et `make test` 12 s plus tard donnent 7 et 471 tests passés, sans aucune erreur de base.
- **Mécanisme, mais dépendant de Linux :** le hook Stop qui ne lance pas `make check`. Lancé à la main pendant un pytest, il a répondu en 0,7 s sans le lancer. Sans `/proc`, il ne voit rien et lance `make check` comme avant ; la base par processus protège alors toujours.
- **Détection heuristique, après coup :** le hook de langue. Le message anglais est déjà affiché quand il réagit, et un message court ou mêlé de français peut passer. Le renvoi à l'arrêt n'a lieu qu'une fois par arrêt, comme pour la procédure.
- **Consigne seulement :** le réglage `language`, la règle 7 de CLAUDE.md, et le plafond de deux passages d'audit. Le hook Stop ne voit que la ligne `Audit spec-auditor : <commit>`, pas le nombre de passages.

### Problèmes rencontrés
- **Mes tests unitaires du hook Stop passaient, et le hook ne marchait pas.** Je l'ai essayé dans une vraie session jetable (`claude -p`, dans le scratchpad) : il laissait s'arrêter un tour en anglais. Au moment du hook Stop, le journal n'a pas encore le dernier message, qui n'arrive que dans le champ `last_assistant_message` de l'entrée du hook. Mes faux journaux, eux, le contenaient. Le hook lit désormais les deux, sans compter deux fois le même message, et l'essai réel renvoie bien au travail, une seule fois.
- **Un avertissement par appel, et non par message.** Plusieurs appels d'outil parallèles qui suivent le même message donnaient chacun un avertissement : 107 sur I11 pour 58 messages. Seul le premier appel en reçoit un maintenant.
- **Le hook PostToolUse n'a pas agi dans la session où je l'ai ajouté.** J'ai écrit exprès un message en anglais avant un appel : aucun avertissement. Rejoué à la main sur le journal de cette session, le hook le détecte, et dans une session neuve il avertit bien. Hypothèse, non vérifiée : Claude Code lit les hooks au démarrage de la session.
- **Le garde-fou `guard_bash.py` a refusé trois de mes commandes**, chaque fois une vérification suivie de `;` ou d'un pipe. Il a fonctionné comme prévu ; je suis passé par des scripts qui rendent le code de retour, ou par une redirection vers un fichier.
- **Le formateur a déplié mes listes de mots en un mot par ligne.** Je les écris maintenant comme une chaîne découpée par `split()`.

### Ce que j'aurais dû savoir dès le départ
- **Un hook se teste dans une vraie session.** Un faux journal ne reproduit que ce que je crois savoir du format, et c'est là que se trouvait le défaut.
- **Une règle qui dépend de ma vigilance ne tient pas dans une longue session.** Deux collisions en I11 malgré la règle de CLAUDE.md, et 71 messages anglais malgré la règle 7. Il faut chercher d'abord le mécanisme.
