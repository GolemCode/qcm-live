# SPEC — QCM Live

Spécification fonctionnelle de référence : la spec initiale enrichie des réponses du commanditaire.

**Règle de traçabilité.**
- Chaque comportement attendu porte un identifiant `[XXX-nn]` et l'incrément qui le livre `(In)`.
- Chaque identifiant doit être vérifié par au moins un test de bout en bout (`tests/e2e`), marqué `@pytest.mark.spec("XXX-nn")`.
- `make verify` échoue si une exigence d'un incrément livré (≤ `[tool.qcm] increment` dans `pyproject.toml`) n'a aucun test E2E passé.

Les éléments marqués *dérivé* ne sont pas dans la spec initiale : ils sont nécessaires pour qu'elle fonctionne.

---

## 1. Contexte d'usage

- Les questions sont projetées au tableau depuis le PC de l'enseignant. Les étudiants répondent sur leur téléphone.
- Dans un premier temps, l'application tourne sur le PC de l'enseignant et les téléphones s'y connectent par le réseau local. L'hébergement en ligne sera décidé plus tard avec le professeur.
- Interface sobre, en français. Rien hors spec.

## 2. Exigences

### Général
- **[GEN-01]** (I0) La page d'accueil s'affiche sur PC et sur téléphone, sans défilement horizontal.

### Enseignant : compte (*dérivé*)
- **[ENS-01]** (I0) L'enseignant se connecte avec son identifiant et son mot de passe. Sans connexion, l'espace enseignant redirige vers la page de connexion. Un mauvais mot de passe est refusé avec un message. L'enseignant peut se déconnecter.

### Enseignant : banque de questions et QCM
- **[BAN-01]** (I1) L'enseignant crée une question **simple** : un énoncé et 2 à 8 propositions, dont exactement une juste.
- **[BAN-02]** (I1) L'enseignant crée une question **multiple** : un énoncé et 2 à 8 propositions, dont au moins une juste. *(précisé en I12)* Aucune proposition juste est permis quand la question propose « Aucune de ces réponses n'est correcte » (BAN-09) : c'est alors la bonne réponse.
- **[BAN-03]** (I1) L'enseignant crée un QCM : un titre et une sélection **ordonnée** d'au moins une question de la banque. Un QCM sans question ne peut pas se lancer. Il peut le devenir après la suppression de ses questions (BAN-07) ; pour le modifier, il faut alors lui redonner au moins une question. *(modifié en I15 : les questions se cochent, l'ordre suit CMP-04)*
  - La liste des QCM et celle du lancement (SES-01) sont **triées par titre**, sans tenir compte des majuscules ni des accents. *(décision du commanditaire, I17 ; majuscules et accents : dérivé)*
- **[BAN-04]** (I1) Une même question de la banque peut servir dans plusieurs QCM.
- **[BAN-05]** (I1) L'enseignant modifie une question : énoncé, type, propositions, bonnes réponses. Les règles de validité sont les mêmes qu'à la création. *(précisé en I12)* Il modifie aussi son barème (BAR-01) et ses options (BAN-09, BAN-10). Une question déjà utilisée dans une session ne se modifie plus : la modifier en crée une nouvelle version (VER-01, I15).
- **[BAN-06]** (I1) L'enseignant modifie un QCM : titre, questions, ordre. *(modifié en I12 : le barème passe aux questions, BAR-01 ; le formulaire de barème du QCM disparaît)* *(modifié en I15 : plus de saisie de rang, l'ordre suit CMP-04)*
- **[BAN-07]** (I1) L'enseignant supprime une question après confirmation. La page de confirmation nomme les QCM qui l'utilisent. La question est retirée de ces QCM.
  - Une question présente dans une session **lancée** ne se supprime plus : elle se **masque**, comme une ancienne version (VER-03). Elle quitte la banque et ses QCM, mais reste comptée dans « déjà posée » (CMP-03). La page de confirmation le dit. Comme une ancienne version, un import ne la partage pas (IMP-07) et un réimport ne la reprend pas (IMP-10). *(décision du commanditaire, I17 ; confirmation et import : dérivé)*
- **[BAN-08]** (I1) L'enseignant supprime un QCM après confirmation. Ses questions restent dans la banque.
- **[BAR-01]** (I12) **Chaque question porte son barème**, écrit comme dans Auto Multiple Choice (AMC) : des directives séparées par des virgules, par exemple `b=2,m=-0.5` ou `haut=2`. Le calcul est celui d'AMC (§3). *(livré en I1 par QCM, passé à la question en I12, décision du commanditaire)*
  - Directives reconnues : `b`, `m`, `v`, `e`, `d`, `p`, `haut`, `mz`, `MAX`, avec des valeurs numériques, éventuellement négatives, au point décimal comme dans AMC. Le formulaire refuse toute autre directive et toute valeur calculée, avec la raison. *(liste validée par le commanditaire)*
  - Une question à choix simple peut aussi donner une valeur à une proposition (AMC-TXT : `-{-2}`) : la choisir rapporte cette valeur. *(validé par le commanditaire)* Le formulaire a une colonne « Points » à cet effet, facultative. *(dérivé)*
  - Barème vide : le barème par défaut d'AMC, `b=1`, `m=0`, `v=0` (par case pour une question multiple). C'est celui d'une question créée à la main. *(décision du commanditaire ; l'import AMC-TXT a ses propres défauts, IMP-04)*
  - À la mise à jour, chaque question reçoit le barème du QCM qui la contenait. Une question présente dans plusieurs QCM aux barèmes différents prend celui du plus ancien QCM. Une question d'aucun QCM garde le barème vide. Les sessions déjà lancées gardent exactement leurs notes. *(décision du commanditaire ; cas des barèmes différents : dérivé)*
- **[BAN-09]** (I12) Une question multiple peut proposer, en dernier, **« Aucune de ces réponses n'est correcte »**, comme le fait AMC (option `CompleteMulti`). Dans le formulaire, c'est une case à cocher. Cette proposition est juste si et seulement si aucune autre ne l'est. Elle compte comme une réponse, pas comme une absence de réponse (`v`). Elle ne compte pas parmi les 8 propositions au plus. *(décision du commanditaire)*
- **[BAN-10]** (I12) Une question peut avoir un **ordre fixe** (AMC : `ordered`) : ses propositions ne sont pas mélangées sur les téléphones (ETU-05). Dans le formulaire, c'est une case « Ne pas mélanger les propositions ». *(décision du commanditaire)*

### Enseignant : groupes d'étudiants
- **[GRP-01]** (I2) L'enseignant importe un groupe d'étudiants : il donne au groupe un nom unique et fournit un fichier CSV (numéro, nom). Le groupe et ses étudiants s'affichent. Les numéros gardent leurs éventuels zéros de tête. *(modifié en I14 : fichier à en-tête `n°`, `numéro étudiant`, `nom`, l'ancien format restant accepté, GRP-05)* *(modifié en I16 : le nom est unique dans son année, GRP-04)*
- **[GRP-02]** (I2) Un CSV invalide est refusé en entier, sans rien créer. Le message désigne chaque ligne fautive (les 20 premières, puis le nombre des autres) : format incorrect, numéro en double, numéro ou nom vide, numéro qui ne contient pas que des chiffres. Un fichier sans étudiant est refusé, de même qu'un nom de groupe vide ou déjà pris. *(modifié en I14 : le numéro étudiant n'est plus tapé sur le téléphone ; il peut être vide et contenir des lettres, GRP-05)*
- **[GRP-03]** (I2) L'enseignant supprime un groupe après confirmation. Pour corriger une liste, il supprime le groupe puis le réimporte.
- **[GRP-05]** (I14) **Fichier à en-tête : `n°`, `numéro étudiant`, `nom`.** Le n° de liste est l'identifiant de l'étudiant dans l'application : c'est lui qui le désigne sur le téléphone, au tableau des connectés et dans les résultats. Le format est décrit au §2 bis. *(décision du commanditaire)*
  - **n°** : entier de 1 à 999, unique dans le groupe ; les n° peuvent ne pas se suivre (un étudiant parti de la liste laisse un trou). *(décision du commanditaire)*
  - **Numéro étudiant** : facultatif, texte libre (chiffres ou lettres), 20 caractères au plus, unique dans le groupe quand il est rempli. *(décision du commanditaire)*
  - **70 étudiants au plus** par groupe : un fichier qui en contient davantage est refusé. *(décision du commanditaire)*
  - **L'ancien format** (deux colonnes, numéro puis nom, en-tête facultatif) reste accepté : le n° est alors le rang dans le fichier (1, 2, 3…), et la première colonne devient le numéro étudiant. *(décision du commanditaire ; rang : dérivé)*
  - La page du groupe affiche le n°, le numéro étudiant et le nom, par n° croissant. *(dérivé)*
- **[MIG-01]** (I14) **Groupes et sessions d'avant I14.** La mise à jour garde les groupes et les sessions existants, en attente, en cours ou terminées. Chaque étudiant reçoit pour n° son rang dans le fichier importé, et son ancien numéro devient son numéro étudiant. Les étudiants déjà connectés à une session le restent, avec leurs réponses ; les notes et le CSV d'une session terminée ne changent que par leurs nouvelles colonnes (RES-05). *(décision du commanditaire ; rang : dérivé)*
- **[MIG-02]** (I16) **Année des groupes et sessions d'avant I16.** Chaque session existante reçoit l'année universitaire de son lancement (de septembre à août). Chaque groupe reçoit celle de la première session lancée avec son nom, sinon l'année universitaire en cours au moment de la mise à jour. L'année d'un groupe se corrige en le supprimant puis en le réimportant (GRP-03) ; celle d'une session reste figée. Rien d'autre ne change : étudiants, réponses et notes. *(décision du commanditaire, I16)*

### Enseignant : import de questions AMC
Les questions viennent de fichiers AMC d'anciens QCM. Aucun fichier réel n'est disponible : l'import suit la documentation d'AMC et son code source (lecteur AMC-TXT et calcul des notes), que j'ai lus. Le format reconnu est détaillé au §2 ter. *(décision du commanditaire : AMC-TXT d'abord, LaTeX ensuite ; un parcours complet passe avant un import exhaustif)*

- **[IMP-01]** (I12) L'enseignant importe un fichier **AMC-TXT**. Avant tout enregistrement, un **récapitulatif** s'affiche : titre du QCM, nombre de questions importées, questions écartées (IMP-03), textes ignorés. L'enseignant confirme, ou annule sans que rien soit créé. Chaque fichier importé devient **un QCM**, avec ses questions dans l'ordre du fichier, et ces questions entrent dans la banque. *(décision du commanditaire)*
  - Titre du QCM : l'option `Title:` du fichier, sinon le nom du fichier sans son extension, sinon « QCM importé ». *(dérivé)*
  - Le récapitulatif indique aussi combien de questions sont déjà dans la banque (IMP-07). *(dérivé)*
  - Fichier de 1 Mo au plus. *(dérivé)*
- **[IMP-02]** (I12) **Une erreur de syntaxe refuse le fichier entier**, sans rien créer. Le message donne le numéro de ligne et la raison de chaque erreur (les 20 premières, puis le nombre des autres, comme pour les groupes, GRP-02). La liste des erreurs de syntaxe est au §2 ter. *(décision du commanditaire)*
- **[IMP-03]** (I12) **Une question valide pour AMC mais non prise en charge ici est écartée** : question ouverte, question numérique ou indicative, directive de barème non gérée, contenu prévu dans un incrément suivant… Le récapitulatif liste chaque question écartée avec son numéro de ligne et la raison, avant que l'enseignant confirme l'import du reste. Ce n'est pas un import partiel silencieux. Un fichier dont toutes les questions sont écartées ne peut pas être importé. *(décision du commanditaire ; liste des cas au §2 ter)*
- **[IMP-04]** (I12) Le barème vient du fichier, question par question, selon les règles d'AMC-TXT. *(décision du commanditaire, règles vérifiées dans le code d'AMC)*
  - Une question prend son propre barème (`*{b=2} …`).
  - Sinon, celui de l'option `DefaultScoringS:` (questions simples) ou `DefaultScoringM:` (multiples) du fichier, qui le remplace sans s'y ajouter.
  - Sinon, si ni la question ni ses propositions n'ont de barème : rien pour une question simple (`b=1`, `m=0`), et **`haut=2`** pour une question multiple. Toutes justes : 2 points ; une case mal traitée : 1 ; deux ou plus : 0.
  - Le barème enregistré sur la question est celui qui s'applique, défaut compris : modifier ensuite la question le montre tel quel (BAR-01). *(dérivé)*
- **[IMP-05]** (I12) Comme AMC, l'import ajoute « Aucune de ces réponses n'est correcte » (BAN-09) à chaque question multiple, sauf si le fichier porte `CompleteMulti: 0`. *(décision du commanditaire ; défaut d'AMC-TXT vérifié dans son code)*
- **[IMP-06]** (I12) **Groupes AMC** (`*(` … `*)`) : leurs questions sont toutes importées, dans l'ordre du fichier. Le mélange et le tirage d'AMC (`shuffle`, `numquestions`) sont ignorés : aucun tirage au hasard. Le nom du groupe (`group=…`) devient l'étiquette de ses questions, affichée dans la banque et dans le QCM. *(décision du commanditaire)*
  - Le texte d'ouverture ou de fermeture d'un groupe n'est pas une question : il est ignoré, et le récapitulatif le cite, avec son numéro de ligne. *(dérivé)*
- **[IMP-07]** (I12) **Une question identique n'est stockée qu'une fois** : elle est partagée entre les QCM qui la contiennent (BAN-04). Identique : même type, même énoncé, mêmes propositions dans le même ordre, mêmes bonnes réponses, même barème, mêmes options. Une question présente deux fois dans un même fichier n'est importée qu'une fois : la seconde est écartée (IMP-03). *(décision du commanditaire ; options et doublon dans un fichier : dérivé)*
  - ~~Réimporter un fichier déjà importé est refusé, avec le nom du QCM qui en vient.~~ *(remplacé en I15 par le réimport, IMP-10)*
- **[IMP-10]** (I15) **Réimporter un fichier** identique, octet pour octet, à celui d'un QCM présent est permis : **il complète ce QCM**. *(décision du commanditaire, après I12)*
  - Chaque question est reconnue par son **origine** : le fichier (son contenu) et son rang parmi les questions retenues. Une question modifiée par l'enseignant, ou remplacée par une nouvelle version (VER-01), reste reconnue et garde la modification. *(décision du commanditaire)*
  - Une question retirée du QCM y est remise ; supprimée de la banque, elle est recréée et remise. Les deux retrouvent leur place du fichier (CMP-04). Le titre du QCM ne change pas. *(décision du commanditaire ; titre : dérivé)*
  - Le récapitulatif nomme le QCM complété et, pour chaque question, « déjà là » ou « ajoutée », et les questions écartées (IMP-03). *(décision du commanditaire)*
  - Un fichier corrigé, au contenu différent, donne un nouveau QCM (IMP-01, IMP-07). Si le QCM venu du fichier a été supprimé, le réimport crée un nouveau QCM, avec les questions reconnues par leur origine. *(décision du commanditaire ; QCM supprimé : dérivé)*
  - Fichier importé avant I15, sans origine enregistrée : au premier réimport, une question identique du QCM (IMP-07) est reconnue, puis une question modifiée l'est à sa place dans le QCM si personne d'autre ne l'occupe. *(décision du commanditaire, I15)*

### Démonstration
- **[DEM-01]** (I12) Le dépôt contient un **fichier AMC-TXT de démonstration**, `demo/qcm-demo.txt`, aux questions fictives. Il sert aux tests et à la démonstration. Il s'importe sans question écartée, et une session menée avec lui va jusqu'aux résultats et au CSV. *(demande du commanditaire)*
  - En I12, il couvre les questions simples et multiples, le barème (par défaut, par question, `DefaultScoringM`, valeur d'une proposition), « Aucune de ces réponses n'est correcte », l'ordre fixe et un groupe. Les formules, le code et une image s'y ajoutent en I17. *(découpage validé, renuméroté après I12)*
  - En I17, il reçoit une formule, du code, une image et de la mise en forme. L'image est dans `demo/images/` : le fichier s'importe alors en archive ZIP du dossier `demo/` (IMP-08), et `make demo` construit cette archive lui-même. *(découpage validé ; archive construite par la commande : dérivé)*
- **[DEM-02]** (I12) Une commande, `make demo`, prépare une **démonstration complète** : un compte enseignant, un groupe d'étudiants fictifs et le QCM importé du fichier de démonstration. *(demande du commanditaire)*
  - Le compte s'appelle `demo`. Un nouveau mot de passe aléatoire est tiré et affiché à chaque lancement : rien de fixe n'est écrit dans le dépôt. *(dérivé)*
  - Relancée, la commande réutilise le groupe et le QCM au lieu d'en créer d'autres. *(dérivé)*
  - Le README décrit pas à pas, dans sa section « Premier cours », le parcours réel : importer, créer le QCM, lancer en mode classe sur eduroam, faire passer, exporter les résultats. *(demande du commanditaire)* *(I13 : ce parcours passe dans le guide de l'enseignant, `GUIDE.md`, et l'installation propose la démonstration, INS-01)*

### Démonstration complète (incrément D)
L'incrément D, hors numérotation, livre DEM-03 à DEM-08 et CNT-05. Données entièrement fictives : le dépôt est public.

- **[DEM-03]** (ID) La **démonstration complète** se lance par une **commande à part**, `qcm-live demo` (en développement : `make demo-complete`). Elle ne met jamais de fausses sessions dans la base de l'enseignant. *(demande du commanditaire)*
  - Elle lance QCM Live en mode classe (CLA-01, INS-03) sur une **base séparée**, `demo.sqlite3` du dossier de données, **recréée à chaque lancement** : rien de ce qu'on y fait ne reste. La base de l'enseignant n'est pas ouverte. *(décision du commanditaire, D)*
  - Compte `demo`, avec un nouveau mot de passe aléatoire affiché dans le terminal à chaque lancement, comme `make demo` (DEM-02). *(décision du commanditaire, D)*
  - Aucune sauvegarde au lancement : SAV-01 ne vaut que pour la base de l'enseignant. *(dérivé)*
  - La préparation refuse une base qui contient déjà un QCM, un groupe ou une session. *(dérivé)*
  - L'installation propose toujours la démonstration légère, sans session (INS-01, DEM-02). *(demande du commanditaire)*
- **[DEM-04]** (ID) La démonstration complète importe **trois fichiers AMC-TXT** fictifs, de **deux matières** (Mathématiques : « Fonctions et dérivées », « Probabilités » ; Informatique : « Python, les bases »), de **20 à 30 questions** chacun. *(demande du commanditaire ; matières et titres : dérivé)*
  - Chaque fichier contient des questions simples et multiples, au moins un barème particulier, « Aucune de ces réponses n'est correcte », un groupe AMC, plusieurs formules, du code et au moins une image ; il s'importe donc en **archive ZIP** (IMP-08), sans question écartée. *(demande du commanditaire)*
  - Ils reprennent les questions de `demo/qcm-demo.txt` qui relèvent de leur matière. Chaque fichier est dans son dossier, `demo-complet/<nom>/`, à part de `demo/` qui se met en ZIP tel quel (DEM-01), avec ses images : ce dossier mis en ZIP s'importe aussi à la main. *(demande du commanditaire ; dossiers : dérivé)*
- **[DEM-05]** (ID) Elle contient **deux groupes de même nom et d'années différentes** (GRP-04) : « L1 Sciences » de l'année en cours, **70 étudiants**, et « L1 Sciences » de l'année précédente, 24 étudiants. *(demande du commanditaire ; nom et effectif du second : dérivé)*
- **[DEM-06]** (ID) Elle contient une **session passée, terminée, avec des réponses** : dès le lancement, ses résultats, son CSV et la Note /20 sont disponibles, et ses questions sont « **déjà posées** » au groupe de l'année en cours (CMP-03), à la composition comme au lancement. *(demande du commanditaire)*
  - La page « Résultats » s'ouvre notes masquées, comme toujours (RES-04) : « d'emblée » veut dire sans avoir à faire passer une session. *(décision du commanditaire, D)*
  - QCM « Fonctions et dérivées », groupe « L1 Sciences » de l'année en cours, lancée sept jours plus tôt ; quelques étudiants absents, et des réponses variées, tirées avec une graine fixe : mêmes résultats à chaque lancement. *(dérivé)*
- **[DEM-07]** (ID) Elle contient un **QCM composé à partir de deux fichiers** (CMP-02), « Mathématiques : révisions », et **une question qui a une nouvelle version** (VER-01) : une question posée lors de la session passée, corrigée ensuite. *(demande du commanditaire ; titre et choix de la question : dérivé)*
- **[DEM-08]** (ID) `GUIDE.md` décrit un **parcours de démonstration de 10 minutes**, à partir de `qcm-live demo`. *(demande du commanditaire)*
  - Chaque libellé cité entre guillemets dans le parcours existe dans l'application. *(dérivé)*

### Composition des QCM et versions des questions (I15 et I16)
I15 livre CMP-01, CMP-02, CMP-04, CMP-05, VER-01 à VER-03 et le réimport (IMP-10) ; I16 livre GRP-04 et CMP-03.

- **[CMP-01]** (I15) Un nouveau QCM se crée en **reprenant un ancien QCM en entier** : mêmes questions, même ordre, nouveau titre. *(décision du commanditaire)*
  - Depuis la fiche du QCM, « Reprendre dans un nouveau QCM » demande le titre, obligatoire. Le nouveau QCM ne vient d'aucun fichier : un réimport complète l'ancien, pas lui (IMP-10). *(dérivé)*
- **[CMP-02]** (I15) L'enseignant **ajoute ou retire des questions**. Les questions ajoutées viennent de la banque, c'est-à-dire des autres QCM importés. Pas de tirage au hasard. *(décision du commanditaire)*
- **[CMP-04]** (I15) La composition se fait par **cases à cocher**, une par question de la banque ; il n'y a plus de rang à saisir. Au moins une case cochée. *(décision du commanditaire, après I12)*
  - Ordre d'un QCM importé : les questions de son fichier suivent leur rang dans ce fichier, si bien qu'une question remise retrouve sa place ; les autres questions viennent à la suite. *(décision du commanditaire)*
  - Ordre d'un autre QCM : les questions gardées restent dans leur ordre, les ajouts vont à la fin, dans l'ordre de la banque. *(dérivé)*
- **[CMP-05]** (I15) Sur la fiche d'un QCM, **« Retirer du QCM »** retire une question de ce seul QCM : elle reste dans la banque et dans les autres QCM. C'est distinct de « Supprimer » dans la banque (BAN-07). *(décision du commanditaire, après I12)*
- **[GRP-04]** (I16) **Un groupe a une année**, obligatoire, par exemple l'année universitaire « 2025-2026 ». Deux groupes peuvent porter le même nom (« ITI4 ») s'ils n'ont pas la même année. Une session fige le nom et l'année de son groupe. *(décision du commanditaire, I16 : l'historique est lié au groupe et à son année, pas au seul nom)*
  - L'année s'écrit « AAAA-AAAA », deux années qui se suivent ; toute autre saisie est refusée : « Année au format 2025-2026 : deux années qui se suivent. » Le champ « Année » de l'import est prérempli avec l'année universitaire en cours (de septembre à août). *(format : décision du commanditaire ; message et préremplissage : dérivé)*
  - Un même nom la même année est refusé : « Un groupe porte déjà ce nom cette année-là. » *(dérivé)*
  - L'année s'affiche à côté du nom : liste et fiche des groupes, choix du groupe au lancement (« ITI4 — 2025-2026 »), tableau en attente, liste des sessions, résultats. *(dérivé)*
  - Dans la liste des groupes et au lancement, les homonymes se suivent, l'année la plus récente d'abord : c'est elle que le lancement présélectionne. *(dérivé)*
- **[CMP-03]** (I16) **Une question déjà posée à un groupe est signalée**, et l'enseignant décide. « Déjà posée » : présente dans une session **démarrée** de ce groupe, cette année-là ; une nouvelle version (VER-01) compte comme la même question. *(décision du commanditaire)*
  - Au lancement d'une session : une page de confirmation liste les questions déjà posées, avec « Lancer quand même » ou « Revenir ».
  - À la composition d'un QCM : l'enseignant choisit un groupe, et les questions déjà posées à ce groupe sont marquées.
  - **Calcul par étudiant** : une question est posée à un étudiant du groupe s'il s'est identifié (ETU-13) dans une session démarrée qui la contenait, sous cette version ou une autre, et dont le groupe figé porte le même nom et la même année. L'étudiant est reconnu par son numéro étudiant quand les deux en ont un, sinon par son nom exact. Un étudiant absent de cette session ne compte pas. *(décision du commanditaire, I16)*
  - La mention donne le nombre d'étudiants du groupe actuel à qui elle a été posée : « posée à 12 étudiants sur 80 ». Une question posée à aucun n'est pas signalée. *(décision du commanditaire)*
  - « Revenir » ramène au formulaire de lancement, rempli comme il l'était ; la page de confirmation, réservée à l'enseignant, montre les énoncés, jamais les propositions. *(dérivé)*
- **[VER-01]** (I15) **Une question déjà utilisée dans une session ne se modifie plus.** La modifier crée une nouvelle version ; l'ancienne reste inchangée pour les résultats et le CSV. La nouvelle version remplace l'ancienne dans les QCM, jamais dans les sessions. *(décision du commanditaire)*
  - « Utilisée » : présente dans une session **lancée**, même jamais démarrée. Les sessions lancées avant I15 sont rattachées aux questions dont le contenu n'a pas changé depuis. *(décision du commanditaire, I15)*
  - Une question jamais utilisée se modifie sur place, dans tous ses QCM, comme avant. Enregistrer sans rien changer ne crée pas de version. *(décision du commanditaire, I15 ; sans changement : dérivé)*
- **[VER-02]** (I15) Avant d'enregistrer une nouvelle version, l'enseignant voit la **liste des QCM touchés**. Il peut limiter le changement au QCM depuis lequel il modifie la question. *(décision du commanditaire)*
  - On modifie une question depuis la fiche d'un QCM par son lien « Modifier ». Limitée à ce QCM, la nouvelle version n'y remplace que lui ; les autres QCM gardent l'ancienne. *(dérivé)*
- **[VER-03]** (I15) **Une ancienne version quitte la liste de la banque**, sauf si un QCM la garde encore (VER-02). La nouvelle version montre ses **versions précédentes**, avec leurs propositions dans l'ordre d'alors (A, B, C…), celui des lettres du CSV. Un import ne partage jamais une ancienne version (IMP-07). *(décision du commanditaire, I15 ; import : dérivé)*

### Contenu : formules, code et images (I17)
- **[CNT-01]** (I17) Les énoncés et les propositions peuvent contenir des **formules mathématiques**, qui s'affichent correctement au tableau et sur le téléphone. *(demande du commanditaire)*
  - Les énoncés et les propositions s'écrivent en **LaTeX léger** (§2 quater), dans le formulaire comme après un import. *(décision du commanditaire, I17)*
  - Les formules sont affichées par KaTeX, servi par l'application : rien ne se charge depuis un autre serveur que le PC de l'enseignant. *(demande du commanditaire, I17)*
  - Une formule que KaTeX ne sait pas afficher apparaît avec son code, soulignée en rouge, au survol la raison. Le serveur ne vérifie pas une formule commande par commande. *(dérivé)*
  - La limite de 200 caractères d'une proposition porte sur son texte en LaTeX léger, commandes comprises. *(dérivé)*
- **[CNT-02]** (I17) Ils peuvent contenir du **code**, en police à chasse fixe, avec ses espaces et ses retours à la ligne. *(demande du commanditaire)*
- **[CNT-03]** (I17) Ils peuvent contenir des **images** PNG, JPEG ou SVG. Une image PDF ou EPS est refusée, avec la raison. *(décision du commanditaire)*
  - Une image s'ajoute par l'import seulement (IMP-08). Le formulaire garde les images de la question et refuse une image inconnue. L'envoi d'une image depuis le formulaire est prévu en I19. *(décision du commanditaire, I17)*
  - Image PDF ou EPS : la question est écartée (IMP-03), avec la raison ; le reste du fichier s'importe. *(décision du commanditaire, I17)*
  - Une image importée n'est jamais supprimée, car une session, une ancienne version ou une question masquée peut la citer. Elle est nommée d'après son contenu : deux imports de la même image la partagent. *(dérivé)*
  - Limites : 2 Mo par image ; SVG sans DTD ni entité. Une image ouverte seule dans le navigateur n'exécute aucun script. Au tableau, sa hauteur est bornée pour que N questions tiennent sans défilement (SES-06). *(dérivé)*
- **[CNT-04]** (I17) Ils peuvent contenir de la **mise en forme** : gras, italique, souligné ; le titre AMC (`[==…==]`) s'affiche en gras. *(décision du commanditaire, I17)*
- **[CNT-05]** (ID) Une formule que KaTeX ne sait pas afficher se voit **dès le récapitulatif de l'import**, en rouge, avant de confirmer ; le guide de l'enseignant, section « Formules qui s'affichent en rouge », explique pourquoi (commande inconnue de KaTeX, macro personnelle, paquet LaTeX) et quoi faire. *(demande du commanditaire)*
- **[IMP-08]** (I17) L'import accepte une **archive ZIP** (le fichier AMC et ses images) ou le fichier seul. Les images s'importent avec le fichier qui les référence ; une image référencée mais absente refuse le fichier. *(décision du commanditaire ; image absente : dérivé)*
  - L'archive contient un seul fichier `.txt` ; les chemins des images partent de son dossier. Les fichiers cachés et `__MACOSX/` sont ignorés. *(dérivé)*
  - Limites : 20 Mo d'archive, 50 Mo une fois décompressée, 500 fichiers. Le fichier seul reste limité à 1 Mo. *(dérivé)*
  - Une image absente est signalée avec la ligne de la question, même si celle-ci serait écartée. *(dérivé)*
  - L'empreinte du réimport (IMP-10) porte sur le fichier et ses images ; sans image, elle est celle du fichier seul, comme avant I17. *(dérivé)*

### Import LaTeX AMC (I18, mis de côté)
- **[IMP-09]** (I18) L'enseignant importe un fichier **LaTeX AMC**, limité à un sous-ensemble documenté : questions simples et multiples, bonnes et mauvaises réponses, groupes, barème, formules, code, images. Comme pour AMC-TXT, une erreur de syntaxe refuse le fichier et une question non prise en charge est écartée. *(à confirmer : ce n'est pas une demande du commanditaire, le professeur utilise des fichiers texte AMC ; I18 est mis de côté, décision du commanditaire, D)*

### Session : lancement et accueil
- **[SES-01]** (I3) L'enseignant lance une session. Il choisit :
  - un QCM, parmi ceux qui ont au moins une question ;
  - un groupe ;
  - le nombre N de questions affichées en même temps, de 1 à 6 (SES-06) ;
  - le temps t par question, de 5 à 600 secondes (30 par défaut).

  Un identifiant de session de 6 chiffres est généré, distinct de ceux des autres sessions. Les sessions lancées sont listées dans l'espace enseignant. *(liste : dérivé)*
- **[SES-06]** (I9) Par défaut, 4 questions s'affichent à la fois. L'enseignant peut choisir une autre valeur au lancement, de 1 à 6 ; elle reste fixe pendant toute la session. *(précision du commanditaire)*
  - Le tableau tient sans défilement en 1920x1080 et en 1280x720 avec 4 énoncés d'environ 200 caractères, ou 6 d'environ 135 (trois colonnes à partir de 5 ; aussi à 3 depuis I10, sur une seule rangée). Au-delà, ou sur un écran plus petit (1024x768), il peut défiler. *(dérivé, I9)*
- **[SES-02]** (I3) Avant le départ, le tableau affiche :
  - l'adresse à ouvrir et l'identifiant de session ;
  - le QCM et le groupe ;
  - les **noms** des étudiants connectés, sans leur numéro, avec le décompte « k / n connectés ». La liste se met à jour en direct, en 2 secondes au plus, sans recharger la page.

  L'enseignant clique sur « Démarrer ». *(dérivé)*
- **[SES-05]** (I8) Avant le départ, le tableau affiche aussi un **QR code pour rejoindre la session**, pour que l'étudiant n'ait à taper ni l'adresse ni le code. Le lire ouvre directement l'écran de cette session sur le téléphone, où il ne reste à saisir que le numéro d'étudiant (ETU-01). *(modifié en I14 : il ne reste qu'à choisir son nom dans la liste, ETU-13)*
  - L'adresse et le code restent affichés en texte, pour un téléphone qui ne lit pas le QR code. *(dérivé)*
  - Le QR code disparaît au démarrage. *(décision I8)* Le tableau en déroulement n'affiche ni le QR code ni l'adresse, seulement le code de session dans son titre : un retardataire (ETU-08) doit obtenir l'adresse autrement, auprès d'un camarade ou de l'enseignant. *(conséquence acceptée, décision I8)*
  - En mode classe, il contient l'adresse du PC sur le réseau local (CLA-01), même si le tableau est ouvert en `localhost`. *(dérivé)*
  - Un téléphone déjà identifié qui le lit retrouve son écran, sans nouvelle saisie (ETU-03). *(dérivé)*
- **[SES-03]** (I3) Le QCM et la liste du groupe sont **figés au lancement**. Modifier ou supprimer ensuite le QCM, ses questions ou le groupe ne change pas la session.
- **[ETU-01]** (I3) L'étudiant ouvre l'application sur son téléphone, à l'adresse projetée. Il saisit l'identifiant de session, puis son numéro d'étudiant, sur le pavé numérique. Son téléphone affiche alors son nom, pour confirmer son identité. *(modifié en I14 : il choisit son nom dans la liste du groupe au lieu de taper un numéro, ETU-13)*
- **[ETU-02]** (I3) Un identifiant de session inconnu est refusé. Un numéro absent du groupe de la session est refusé. Un numéro déjà utilisé dans la session, depuis un autre appareil, est refusé : il reste lié à ce premier appareil, sauf si l'enseignant le libère avant le démarrage (SES-04). *(modifié en I14 : c'est l'étudiant, désigné par son n°, qui est déjà pris ; ETU-13)*
- **[SES-04]** (I4) Avant le démarrage, l'enseignant peut **libérer un numéro**. Il le fait depuis une page de gestion des connectés, ouverte depuis le tableau mais non projetée, qui montre les numéros et les noms. L'appareil qui occupait le numéro perd son identité, et le vrai étudiant peut alors le saisir. Après le démarrage, aucune libération n'est possible. *(modifié en I14 : la page montre le n° et le nom, plus le numéro étudiant ; on libère un étudiant, qui peut de nouveau choisir son nom)*
- **[ETU-03]** (I3) Un téléphone rechargé ou sorti de veille retrouve l'identité de l'étudiant, sans nouvelle saisie. Ressaisir l'identifiant de la session mène aussi directement à son écran.
- **[ETU-13]** (I14) **L'étudiant choisit son nom dans la liste du groupe.** Sans identité, l'écran de la session liste les étudiants du groupe figé (SES-03), chacun avec son n°, par n° croissant. Aucun numéro n'est à taper, et aucun n'est projeté. *(décision du commanditaire)*
  - Un champ « Rechercher votre nom » filtre la liste pendant la saisie, sans tenir compte des majuscules ni des accents. Sans JavaScript, le champ n'apparaît pas et la liste entière reste utilisable. *(décision du commanditaire ; sans JavaScript : dérivé)*
  - Toucher son nom ouvre une confirmation, « Vous êtes … ? », avec le nom et le n°, puis « Oui, c'est moi » ou « Non, revenir à la liste ». L'étudiant n'est identifié qu'après « Oui, c'est moi ». *(décision du commanditaire)*
  - Un étudiant déjà identifié sur un autre appareil reste dans la liste, grisé, avec « déjà connecté », et ne se choisit pas. S'il est pris pendant la confirmation, « Oui, c'est moi » est refusé avec un message, et la liste revient. Il reste lié à ce premier appareil, sauf libération par l'enseignant avant le démarrage (SES-04). *(décision du commanditaire ; prise pendant la confirmation : dérivé)*
  - Le téléphone affiche ensuite le nom et le n° de liste, jamais le numéro étudiant (VIS-04). *(décision du commanditaire)*

### Session : déroulement
- **[DER-01]** (I4) Après le démarrage, les questions défilent **par groupes de N**, dans l'ordre du QCM ; le dernier groupe peut en compter moins. Au tableau, chaque question du groupe affiche, sur sa **couleur de fond** et avec son **numéro de couleur** (1 à N) et sa forme (AFF-03), son énoncé seul (AFF-01). Le contenu affiché est celui qui a été figé au lancement (SES-03). À la fin du dernier créneau, le tableau indique que la session est terminée.
- **[DER-02]** (I4) Un groupe de n questions se déroule en n **créneaux** synchronisés de t secondes, identiques pour tous. À la fin du temps, on passe automatiquement au créneau suivant, sans recharger à la main : le tableau et les téléphones suivent en 2 secondes au plus. Il n'y a pas de pause ; depuis I16, l'enseignant peut terminer le créneau en cours (TPS-02). Le temps restant s'affiche au tableau et sur les téléphones. Après le dernier créneau, les téléphones indiquent que la session est terminée.
- **[ETU-04]** (I4) Pendant un créneau, le fond du téléphone prend la couleur de la question à laquelle l'étudiant doit répondre, avec son numéro de couleur et sa forme (AFF-03). Seules les propositions s'affichent, sans lettre et **jamais l'énoncé** :
  - question simple : on en choisit une ;
  - question multiple : on coche une ou plusieurs cases.

  Chaque choix est enregistré aussitôt, sans bouton à valider, et le téléphone confirme l'enregistrement. *(enregistrement immédiat : dérivé)*
- **[ETU-05]** (I4) Sur chaque téléphone, les propositions sont mélangées. L'ordre est propre à l'étudiant et reste stable pour une question donnée. *(précisé en I9)* Il reste le même quand le téléphone recharge la page ou revient sur la session, et la note ne dépend pas de l'ordre affiché : une réponse désigne une proposition, pas sa place à l'écran.
  - Exceptions *(I12)* : une question à ordre fixe (BAN-10) garde l'ordre de la banque, et « Aucune de ces réponses n'est correcte » reste toujours en dernier (ETU-12).
  - L'ordre est tiré au hasard, indépendamment pour chaque étudiant. L'application ne sait pas qui est assis à côté de qui : deux étudiants qui ont la même question au même moment peuvent voir une proposition au même endroit (1 fois sur 4 avec 4 propositions). Une répartition qui l'éviterait entre étudiants connectés à la suite a été écartée, rien ne garantissant que des voisins de table se connectent l'un après l'autre. *(décision I9)*
- **[ETU-06]** (I4) Tous les étudiants répondent à toutes les questions, mais pas dans le même ordre : à chaque créneau d'un groupe, chacun a une autre question du groupe (rotation). Si N=1, l'ordre est forcément le même pour tous.
- **[ETU-07]** (I4) L'étudiant peut changer sa réponse jusqu'à la fin du créneau ; c'est la dernière qui compte. Un téléphone rechargé réaffiche la réponse enregistrée. Après la fin du créneau, toute réponse est refusée par le serveur, et le téléphone le signale.
- **[ETU-08]** (I4) Un étudiant peut rejoindre une session déjà commencée. Les créneaux qu'il a manqués comptent comme non-réponse.
- **[ETU-09]** (I5) Sur une question simple, l'étudiant peut **effacer sa réponse** jusqu'à la fin du créneau, avec le bouton « Effacer ma réponse » : plus aucune proposition n'est choisie, le téléphone confirme l'effacement et la question compte comme non-réponse (v). Sur une question multiple, décocher toutes les cases revient au même. Après la fin du créneau, l'effacement est refusé comme toute réponse (ETU-07). *(dérivé : le téléphone affiche « Réponse effacée » ; le bouton est inactif quand aucune proposition n'est choisie)*
- **[ETU-10]** (I11) **Réseau lent.** Chaque choix part aussitôt (ETU-04). Tant que le serveur ne l'a pas confirmé, le téléphone affiche « Envoi en cours… » ; « Réponse enregistrée » n'apparaît qu'après sa confirmation. Si l'envoi échoue faute de réseau, le téléphone renvoie seul la dernière réponse, chaque seconde, tant que le créneau dure. *(validé par le commanditaire)*
  - Une réponse que le serveur n'a pas enregistrée avant la fin de son créneau est signalée clairement comme non enregistrée, jamais comme enregistrée. Si le téléphone affiche encore ce créneau, il le dit sur le moment (ETU-07) ; sinon, il le dit dès l'écran suivant : « Votre réponse précédente n'a pas été enregistrée. » *(décision du commanditaire ; message de l'écran suivant : dérivé)*
  - Le téléphone garde la trace de ses envois dans le navigateur (stockage local), pour la retrouver après un rechargement ou au créneau suivant. Il demande au serveur ce qui a vraiment été enregistré : une réponse arrivée à temps compte comme transmise, même si le téléphone n'a pas vu la confirmation. *(dérivé)*
  - Rechargé pendant le même créneau alors qu'un envoi est encore en attente, le téléphone réaffiche ce dernier choix, avec « Envoi en cours… », et continue de l'envoyer. Sans envoi en attente, il réaffiche la réponse enregistrée (ETU-07). *(décision du commanditaire, I11)*
- **[ETU-12]** (I12) Sur le téléphone, « Aucune de ces réponses n'est correcte » (BAN-09) s'affiche en dernier. Elle exclut les autres cases : la cocher décoche les autres, et cocher une autre case la décoche. Le serveur refuse une réponse qui la combine avec une autre proposition. La cocher seule est une réponse : elle est enregistrée et confirmée comme les autres. *(décision du commanditaire ; refus du serveur : dérivé)*
- **[ETU-11]** (I11) Quand le téléphone n'obtient plus de réponse du serveur depuis 3 secondes, il affiche « Connexion perdue ». Le message disparaît dès que la connexion revient. *(validé par le commanditaire ; délai : dérivé)*
- **[DER-03]** (I4) Le tableau n'affiche ni la correction ni de statistiques pendant la session, hormis, depuis I16, le décompte « k / n ont répondu » (DER-04).
- **[DER-04]** (I16) Pendant le déroulement, le bandeau du tableau affiche « k / n ont répondu » pour le créneau en cours : n est le nombre d'étudiants connectés à la session, k celui des connectés dont une réponse est enregistrée pour leur question de ce créneau. Une réponse effacée (ETU-09) ne compte pas. Le décompte se met à jour en 2 secondes au plus, sans recharger la page, et repart du créneau suivant à son début. Il ne fait connaître ni énoncé ni proposition (AFF-01). *(décision du commanditaire, I16)*

- **[AFF-01]** (I9) **Une capture d'écran ou une photo ne contient jamais à la fois une question et ses réponses.** À aucun moment de la session, le tableau n'affiche ni ne reçoit une proposition de réponse, et le téléphone n'affiche ni ne reçoit un énoncé (ETU-04). Les pages des résultats et le CSV ne contiennent ni énoncé ni proposition.
  - Les pages de la banque de questions et des QCM, réservées à l'enseignant et sans rapport avec le déroulement, montrent encore l'un et l'autre, puisqu'elles servent à les rédiger. L'enseignant ne les projette pas pendant une évaluation. *(dérivé)*
- **[AFF-02]** (I9) Au tableau, une question à réponses multiples porte la mention « Plusieurs réponses possibles » sous son énoncé. Une question simple n'a aucune mention. *(forme choisie par le commanditaire : texte seul, sans le ♣ d'AMC)*
- **[AFF-03]** (I9) Chaque couleur a, en plus de son numéro, une **forme** qui lui est propre, au tableau comme sur le téléphone : 1 ● rond, 2 ▲ triangle, 3 ■ carré, 4 ◆ losange, 5 ★ étoile, 6 ✚ croix. Il n'y a qu'un affichage, lisible par tous, sans mode à activer. *(choix des formes : proposé en I9, validé)*
- **[AFF-04]** (I9) Les six couleurs sont celles de la palette d'Okabe et Ito, conçue pour rester distincte dans les principaux types de daltonisme, dans cet ordre : 1 jaune `#F0E442`, 2 bleu `#0072B2`, 3 vert bleuté `#009E73`, 4 bleu ciel `#56B4E9`, 5 pourpre `#CC79A7`, 6 orange `#E69F00`. Tout texte affiché sur une couleur, au tableau comme sur le téléphone, a un contraste d'au moins 4,5:1 (texte blanc sur le bleu). *(décision I9)*
  - Ordre choisi pour N = 4, la valeur par défaut : les 4 premières couleurs restent distinctes en vision normale, en protanopie, deutéranopie et tritanopie simulées, sur un projecteur délavé, et même en niveaux de gris. Au-delà de 4, la forme et le numéro départagent les couleurs que la simulation rapproche. *(décision I9, mesures dans REX.md)*
  - L'ancienne palette confondait le jaune et l'orange (1 et 5) en deutéranopie et sur projecteur, le bleu et le violet (2 et 6) en protanopie, et ses six couleurs avaient presque la même luminosité. *(constat I9)*

### Présentation et accessibilité (refonte visuelle)
Direction « Signalétique », choisie par le commanditaire parmi trois maquettes (I10). Découpage : socle et tableau (I10), téléphone (I11), espace enseignant (I19, après l'import AMC et la composition des QCM : §5 bis).

- **[VIS-01]** (I10) L'interface suit la direction « Signalétique » : encre sur papier, bandeau noir, filets épais, majuscules espacées pour les étiquettes. La police est Atkinson Hyperlegible Next, dessinée pour les lecteurs malvoyants : elle distingue les caractères proches (I, l, 1 ; O, 0), utile pour un code de session et des numéros d'étudiant.
  - La police est servie par l'application : aucune page ne demande quoi que ce soit à un autre serveur, la salle n'ayant pas forcément accès à Internet. *(dérivé)*
  - Les énoncés sont en graisse normale ; le gras est réservé aux numéros, aux étiquettes et aux titres. *(demande du commanditaire, I10 : vérifier au tableau la lisibilité d'un énoncé d'environ 200 caractères ; résultat dans REX.md)*
  - Le code s'affiche en police à chasse fixe (Atkinson Hyperlegible Mono), les formules en police KaTeX ; formules, code et images arrivent en I17 (CNT-01 à CNT-04). *(décision du commanditaire, I10)*
- **[VIS-02]** (I10) Au tableau, pendant le déroulement, un bandeau porte le code de session, la position dans le QCM (« Questions 5–8 sur 24 », ou « Question 5 sur 24 » pour un groupe d'une seule question), le temps restant en minutes et secondes (« 0:18 ») et le bouton « +10 s ». Sous le bandeau, une barre montre la part du créneau qui reste : elle se vide jusqu'à l'échéance et tient compte du temps ajouté (TPS-01). *(validé par le commanditaire, I10)*
  - Le temps restant s'écrit de la même façon sur le téléphone. *(dérivé)*
  - Le tableau, projeté, n'a ni la navigation de l'espace enseignant ni le bouton de déconnexion : son logo ramène à la liste des sessions, et « Gérer les connectés » reste dans le bandeau à toute phase (SES-04). *(décision I10, d'après la maquette validée)*
  - De 1 à 6 questions à la fois, le tableau tient sans défilement en 1920x1080 et en 1280x720, avec des énoncés d'environ 200 caractères jusqu'à 4 questions, et d'environ 135 à 5 et 6 (SES-06). *(dérivé)*
  - Les énoncés mesurent au moins 2,5 % de la hauteur de l'écran (27 px en 1080 lignes), pour rester lisibles du fond de la salle. *(dérivé)*
- **[VIS-03]** (I10) Au tableau, avant le départ : l'adresse à ouvrir, le code de session en grands chiffres (au moins 8 % de la hauteur de l'écran) groupés par trois, le QR code (« ou scannez »), le QCM, le groupe et les réglages, puis le décompte des connectés, avec une barre de remplissage, et leurs noms en colonnes (SES-02, SES-05). Avec un groupe de 40 étudiants tous connectés, il tient sans défilement en 1280x720, bouton « Démarrer » compris. À la fin, il affiche « Session terminée. » et le lien vers les résultats. *(dérivé)*
- **[ACC-01]** (I10) L'accessibilité des pages communes (accueil, connexion, pages d'erreur) et du tableau, dans ses trois phases, est vérifiée par des tests :
  - aucune violation des règles WCAG 2.1, niveaux A et AA, que détecte axe-core ;
  - un contraste d'au moins 4,5:1 pour tout texte affiché (la mesure d'AFF-04, étendue à ces pages) ;
  - chaque lien, bouton et champ s'atteint au clavier, avec la touche Tab, et montre un indicateur de focus d'au moins 2 px, contrasté d'au moins 3:1 avec le fond.

  Le téléphone suivra en I11, l'espace enseignant en I19. Un contrôle automatique ne trouve qu'une partie des défauts : il ne remplace pas un essai avec un lecteur d'écran, qui reste à faire. *(dérivé)*

- **[VIS-04]** (I11) Le téléphone suit la direction « Signalétique » dans tous ses états : saisie du code et du numéro *(I14 : choix du nom, ETU-13)*, attente, déroulement, envoi, perte de connexion, fin. *(validé par le commanditaire)*
  - Un bandeau noir porte « QCM Live » et, dès que la session est connue, son code groupé par trois.
  - En attente : « Vous êtes », le nom en grand, le numéro, puis « En attente du démarrage ». *(I14 : le n° de liste)*
  - En déroulement :
    - en haut, le numéro et la forme de la couleur, avec « Couleur N » ;
    - le temps restant en minutes et secondes (VIS-02), avec une barre qui se vide jusqu'à l'échéance et tient compte du temps ajouté (TPS-01) ;
    - la proposition choisie passe en noir plein, texte blanc ;
    - l'état de l'envoi et « Effacer ma réponse » sont en bas de l'écran, à portée du pouce, et y restent visibles quand les propositions font défiler la page ;
    - en pied, le nom et le numéro de l'étudiant. *(I14 : le n° de liste)*
  - Toute cible tactile (proposition, bouton, champ) mesure au moins 48 px de haut et de large. *(dérivé)*
  - Aucun défilement horizontal, en Pixel 7 comme sur un petit téléphone de 360 px de large. *(dérivé)*
- **[ACC-02]** (I11) Les vérifications d'ACC-01 (axe-core, contraste, clavier) s'appliquent à tous les états du téléphone, sur un Pixel 7. *(dérivé)*

### Session : temps additionnel
- **[TPS-01]** (I5) Pendant un créneau, l'enseignant peut ajouter 10 secondes depuis son PC. Le temps restant augmente de 10 s au tableau et sur tous les téléphones, et les créneaux suivants sont décalés d'autant. Les ajouts se cumulent. Une réponse envoyée pendant le temps ajouté est acceptée. Le bouton « +10 s » est sur le tableau, pendant le déroulement seulement ; un clic arrivé après la fin du créneau n'ajoute rien. *(emplacement et clic tardif : dérivé)*
- **[TPS-02]** (I16) **Terminer le créneau en cours.** Dans le bandeau du tableau, pendant le déroulement, le bouton « Terminer le créneau » devient « Confirmer » au premier clic, pendant 3 secondes, puis reprend son libellé. Un clic sur « Confirmer » ramène le temps restant à 5 secondes, au tableau et sur tous les téléphones, et avance d'autant les créneaux suivants. *(décision du commanditaire)*
  - S'il reste 5 secondes ou moins, rien ne change. Un clic arrivé après la fin du créneau ne change rien non plus (comme TPS-01). *(dérivé)*
  - « +10 s » reste possible ensuite et s'ajoute à ces 5 secondes : c'est le rattrapage d'un clic malheureux. *(décision du commanditaire)*
  - Sur le dernier créneau, la session se termine au bout de ces 5 secondes. *(décision du commanditaire, I16)*

### Fin de session et résultats
- *FIN-01 (livrée en I6, retirée en I8).* Le QR code des réponses, affiché en fin de session sur le téléphone, est retiré avec l'accord du professeur : son but n'avait jamais été établi. L'identifiant n'est pas réattribué.
- **[FIN-02]** (I11) À la fin de la session, le téléphone indique que la session est terminée : ni QR code, ni réponses, ni note. *(livrée en I8, précisée en I11)*
  - Il ajoute « Vos réponses ont été transmises à l'enseignant. » seulement si toutes les réponses de l'étudiant ont été confirmées par le serveur. Sinon, il indique combien n'ont pas pu être transmises et invite l'étudiant à le signaler à l'enseignant. *(décision du commanditaire, I11)*
  - Une réponse compte une fois par créneau : c'est la dernière donnée qui doit avoir été enregistrée (ETU-07). *(dérivé)*
  - Un téléphone qui n'a donné aucune réponse, ou dont le navigateur a perdu la trace de ses envois (stockage effacé, navigation privée refermée), n'affiche que « Session terminée. » : il ne peut rien affirmer. Un téléphone non identifié non plus. *(dérivé)*
- **[RES-01]** (I6) L'enseignant voit le tableau des résultats de la session : numéro, nom, note et note maximale. *(I14 : n°, numéro étudiant, nom, RES-05)* La note suit le barème AMC de chaque question (§3), figé au lancement. *(par question depuis I12)*
  - Les résultats sont sur une **page non projetée**, disponible une fois la session terminée. On l'ouvre depuis le tableau ou depuis la liste des sessions, qui indique l'état de chaque session (en attente, en cours, terminée). Avant la fin, la page n'affiche ni étudiant ni note. *(décision I6)*
  - Le lien « Résultats » n'apparaît, au tableau comme dans la liste des sessions, qu'une fois la session terminée. *(dérivé)*
  - Tous les étudiants du groupe figé sont listés, dans l'ordre du fichier importé *(I14 : par n°, RES-05)*. Ceux qui ne se sont jamais connectés sont marqués **« Absent »**, sans note. Un étudiant connecté qui n'a rien répondu n'est pas absent : chaque question lui vaut v. *(décision I6)*
  - Les nombres s'écrivent à la française, sans zéro inutile (1,75 ; 3 ; -0,5). *(dérivé)*
- **[RES-02]** (I6) L'enseignant télécharge les résultats en CSV : une ligne par étudiant, avec la note et, pour chaque question, la réponse donnée et les points obtenus.
  - Format d'Excel en français : séparateur point-virgule, virgule décimale, UTF-8 avec BOM. Fichier `resultats-<code>.csv`. *(décision I6)*
  - Le CSV n'est téléchargeable qu'une fois la session terminée. *(dérivé)*
  - Le numéro est écrit tel quel. Excel, à l'ouverture, en retire les zéros de tête : on peut reformater la colonne en texte. *(décision I6)*
  - Colonnes : `numéro`, `nom`, `note`, `note max`, puis, pour chaque question dans l'ordre du QCM, `Qn réponse` et `Qn points`. Une réponse s'écrit avec les lettres des propositions dans l'ordre de la banque au moment du lancement (A pour la première), `-` signifie aucune réponse. *(précisé en I9 : le tableau n'affiche plus ces lettres)* Tant que la question n'a pas été modifiée, ce sont les lettres de la liste des questions. Après une modification (BAN-05), plus aucune page ne montre l'ordre figé : voir §5 bis. *(constat I9 ; résolu en I15 : les versions précédentes montrent cet ordre, VER-03)* « Aucune de ces réponses n'est correcte » prend la lettre qui suit la dernière proposition, comme dans la banque. *(dérivé, I12)* Un absent a `Absent` pour note et des cellules de questions vides. *(dérivé)* *(I13 : colonne `note /20` après `note max`, RES-03)* *(I14 : `n°`, `numéro étudiant`, `nom` au lieu de `numéro`, `nom`, RES-05)*
  - Un nom ou un numéro qui commence par `=`, `+`, `-`, `@`, une tabulation ou un retour chariot est précédé d'une apostrophe, pour qu'un tableur n'exécute aucune formule. Les nombres calculés (notes, points) ne le sont jamais. *(dérivé)*
- **[RES-03]** (I13) **Note sur 20.** Le CSV porte une colonne `note /20` juste après `note max`, et la page des résultats une colonne « Note /20 » : total obtenu ÷ total maximal du QCM figé × 20. *(décision du commanditaire)*
  - Arrondie au centième le plus proche (un demi-centième est arrondi vers le haut), puis bornée entre 0 et 20, en virgule décimale. *(décision du commanditaire ; demi-centième : dérivé)*
  - Les bornes servent : une note peut dépasser la note maximale (valeur d'une proposition, directive `MAX`) ou être négative (§3). *(constat signalé au commanditaire)*
  - Cellule vide pour un absent, et aussi quand le total maximal est nul ou négatif. La colonne `note` reste inchangée. *(décision du commanditaire)*
- **[RES-04]** (I13) L'écran du PC est dupliqué sur le projecteur : tout ce qui s'y ouvre est projeté. La page des résultats s'ouvre donc **notes masquées**, avec un bouton « Afficher les notes ». Le lien du CSV télécharge le fichier sans rien afficher. *(décision du commanditaire)*
  - Masqué : tout le tableau des résultats, noms compris. *(dérivé)*
- **[RES-05]** (I14) **Le n° de liste dans les résultats.** La page des résultats et le CSV commencent par le n°, le numéro étudiant et le nom : colonnes `n°`, `numéro étudiant`, `nom`, puis `note`, `note max`, `note /20` et les questions (RES-02, RES-03). Une ligne par étudiant du groupe figé, par n° croissant. *(décision du commanditaire ; ordre : dérivé)*
  - Un numéro étudiant vide laisse sa cellule vide. Comme le nom, le numéro étudiant est un texte venu de l'extérieur : il est neutralisé pour le tableur (RES-02). *(dérivé)*

### Mode classe
- **[CLA-01]** (I7) L'application se lance en mode classe sur le PC de l'enseignant : serveur de production local, sans mode debug. Elle fonctionne de bout en bout depuis les téléphones du réseau local, et l'adresse à ouvrir s'affiche.
  - Une commande : `make classe` (port 8000 par défaut). Le mode debug est toujours désactivé, quel que soit le réglage de `.env`. *(dérivé)* *(I13 : l'enseignant lance `qcm-live`, INS-03 ; `make classe` reste pour le développement)*
  - L'adresse à ouvrir sur les téléphones est celle du PC sur le réseau local (par exemple `http://192.168.1.23:8000/`). Elle s'affiche dans le terminal, avec celle de l'espace enseignant, et le tableau la projette (SES-02) même s'il est ouvert en `localhost`. *(dérivé)*
  - Si la détection choisit la mauvaise interface réseau, l'enseignant impose l'adresse (`ADRESSE=…`). *(dérivé)* *(I13 : il la choisit aussi sans redémarrer, CLA-02)*
  - En mode classe, l'espace enseignant (connexion, notes, pilotage) ne s'ouvre que sur le PC de l'enseignant ; depuis un autre appareil, il est refusé. *(décision du commanditaire, définitive)* Les étudiants partagent le réseau du serveur, et la connexion passe en clair (HTTP). *(dérivé)*
  - Toute une classe (40 téléphones) peut valider son numéro *(I14 : confirmer son nom)*, puis répondre, au même instant, sans qu'aucune requête échoue. *(dérivé)*
  - Hors mode debug, les pages d'erreur (page introuvable, requête refusée, formulaire expiré, erreur du serveur) sont en français, comme le reste de l'interface. *(dérivé)*
- **[CLA-02]** (I13) **Adresses du PC.** Au démarrage, le terminal affiche l'adresse retenue pour les téléphones, puis les autres adresses du PC, chacune avec le nom de sa carte réseau. L'enseignant en choisit une autre **sans redémarrer** : au tableau en attente, le lien « Changer d'adresse » ouvre la page « Réseau », qui liste les adresses avec leur carte. Le tableau projette ensuite l'adresse choisie, dans le texte comme dans le QR code (SES-05). *(décision du commanditaire)*
  - Adresse retenue d'office : celle d'un partage de connexion ouvert par le PC lui-même (192.168.137.1 sous Windows, 10.42.0.1 sous Linux), puisque les téléphones y sont ; sinon celle de la route par défaut ; sinon une autre adresse privée. Les réseaux virtuels (Docker, machines virtuelles, VPN) passent en dernier. La boucle locale et les adresses automatiques (169.254.x.x) sont écartées. *(dérivé ; le PC peut être relié au partage d'un téléphone ou partager lui-même sa connexion, décision du commanditaire)*
  - Le choix vaut jusqu'à l'arrêt de l'application. Une carte réseau apparue après le lancement demande de relancer, et la page « Réseau » le dit. *(dérivé)*
- **[CLA-03]** (I13) **Pare-feu.** Au démarrage et sur la page « Réseau », l'application signale un pare-feu qui peut bloquer les téléphones : ufw ou firewalld actif sous Linux, réseau classé « Public » sous Windows. Elle affiche la commande ou la marche à suivre pour ouvrir le port utilisé. **Elle n'ouvre jamais le pare-feu elle-même.** *(décision du commanditaire)*
  - La détection ne fait que lire : sans droit administrateur, elle ne voit pas les règles du pare-feu. L'avertissement dit donc « peut bloquer », et le test du téléphone (CLA-04) tranche. *(dérivé)*
- **[CLA-04]** (I13) **Tester avec mon téléphone.** Depuis le tableau en attente ou l'espace enseignant, la page « Réseau » affiche un QR code d'essai, bâti sur l'adresse projetée. Un téléphone qui le lit affiche « Connexion réussie », et la page du PC passe à « Téléphone connecté ». *(décision du commanditaire)*

### Installation, lancement et sauvegarde
Plateforme cible : Linux, sur le PC personnel de l'enseignant, avec droits administrateur et Internet à l'installation. Windows doit fonctionner, en second. *(décision du commanditaire)*

- **[INS-01]** (I13) **Installation en une commande** sous Linux, copiée depuis le guide de l'enseignant (`GUIDE.md`), sans make ni git, et sans droit administrateur. *(décision du commanditaire)*
  - Elle installe uv dans le dossier de l'utilisateur s'il manque, récupère l'application, prépare la base et crée le compte de l'enseignant. *(décision du commanditaire)*
  - Elle demande si l'on veut l'exemple de démonstration (groupe et QCM fictifs, DEM-02), sans rien lancer. *(décision du commanditaire)*
  - Elle ajoute la commande `qcm-live` et une icône « QCM Live » au menu des applications. *(décision du commanditaire)*
  - Les données (base, clé secrète) quittent le dossier de l'application : elles sont dans `~/.local/share/qcm-live/`, lisible par l'utilisateur seul. *(décision du commanditaire ; emplacement et droits : dérivé)*
  - Sous Windows, une commande PowerShell fait de même, avec un raccourci au menu Démarrer. *(dérivé ; vérifié seulement par l'essai du commanditaire, aucun Windows n'étant disponible pour les tests : réussi après I13, PC relié au partage d'un téléphone)*
- **[INS-02]** (I13) Relancée, la même commande **met à jour** l'application sans toucher aux données : la base et le compte restent, et la question de la démonstration n'est plus posée. *(décision du commanditaire)*
- **[INS-03]** (I13) **Un seul lancement** : l'icône « QCM Live » ou la commande `qcm-live` lance toujours le mode classe (CLA-01) et ouvre le navigateur sur l'espace enseignant. Le terminal affiche l'adresse des téléphones et cite le guide de l'enseignant. `make run` ne sert plus qu'au développement. *(décision du commanditaire)*
  - Si le port est déjà pris, par exemple parce que QCM Live est déjà lancé, le message le dit. *(dérivé)*
- **[SAV-01]** (I13) **À chaque lancement**, `qcm-live` sauvegarde les données dans le dossier `~/QCM Live/sauvegardes/`, avant toute mise à jour de la base. Les 10 dernières sauvegardes sont gardées. Aucun autre fichier du dossier n'est touché. *(décision du commanditaire ; avant la mise à jour de la base : dérivé)*
  - Une sauvegarde est un fichier `qcm-live-<date>-<heure>.zip`. Les images, enregistrées dans la base, y entrent avec elle (I17). *(dérivé)*
- **[SAV-02]** (I13) `qcm-live sauvegarder` fait une sauvegarde à la demande. `qcm-live restaurer` remet les données d'une sauvegarde, choisie dans la liste ou désignée par son chemin, après confirmation. *(décision du commanditaire)*
  - Les données remplacées sont d'abord sauvegardées, pour qu'une restauration se rattrape. *(dérivé)*
  - Une archive qui n'est pas une sauvegarde de QCM Live, qui est abîmée ou qui vient d'une version plus récente de l'application est refusée, sans rien changer. *(dérivé)*

## 2 bis. Format du CSV d'un groupe (*dérivé*, réécrit en I14)

- **Nouveau format (I14, GRP-05).** Une ligne d'en-tête, `n°;numéro étudiant;nom`, puis une ligne par étudiant : n°, numéro étudiant, nom (par exemple `12;21904567;DUPONT Jeanne`, ou `13;;MARTIN Paul` sans numéro étudiant).
  - L'en-tête est reconnu sans tenir compte des majuscules, des accents ni des espaces en trop ; `no` et `nº` valent `n°`. Un fichier à trois colonnes sans cet en-tête est refusé.
  - **n°** : de 1 à 3 chiffres de 0 à 9, valeur de 1 à 999, unique dans le fichier.
  - **Numéro étudiant** : vide, ou de 1 à 20 caractères sans caractère de contrôle, unique dans le fichier quand il est rempli. Il est gardé tel quel (zéros de tête compris).
- **Ancien format (I2), toujours accepté.** Deux colonnes, numéro puis nom, sans en-tête obligatoire. Le n° est le rang de l'étudiant dans le fichier (1 pour le premier), et le numéro devient le numéro étudiant, avec les mêmes règles que ci-dessus *(I14 : il n'a plus à ne contenir que des chiffres ni à être rempli)*.
  - **En-tête facultatif.** La première ligne non vide est un en-tête si elle a deux colonnes remplies et si sa première ne contient aucun chiffre (par exemple « numéro;nom »). Le message de confirmation de l'import cite la ligne ainsi ignorée.
- **Nom.** De 1 à 200 caractères, sans caractère de contrôle. Deux étudiants peuvent porter le même nom : leur n° les distingue.
- **70 étudiants au plus** (GRP-05).
- **Séparateur.** Point-virgule, comme dans les exports d'Excel en français, ou virgule. On retient le point-virgule s'il apparaît dans la première ligne non vide.
- **Tolérances.** Les lignes vides et les colonnes vides en fin de ligne sont ignorées.
- **Encodage.** UTF-8, avec ou sans BOM, ou Windows-1252 pour les anciens exports d'Excel.
- **Numéros de ligne.** Ceux des messages d'erreur sont ceux du fichier, en commençant à 1.

## 2 ter. Format AMC-TXT reconnu (I12, *dérivé* de la documentation et du code d'AMC)

Le lecteur suit les règles du lecteur AMC-TXT d'AMC (`AMC::Filter::plain`) : mêmes formes de ligne, mêmes options, mêmes contrôles. Il est plus strict là où AMC ignorerait un élément sans le dire.

- **Lignes.**
  - `#` en début de ligne : commentaire.
  - `Option: valeur` : option du fichier ; la valeur se poursuit sur les lignes suivantes.
  - `*` : question simple ; `**` : question multiple. Après les étoiles, facultatifs et dans cet ordre : `<…>` (question ouverte), `[options]`, `{barème}`, puis l'énoncé.
  - `+` : proposition juste ; `-` : proposition fausse. Facultatifs : `[lettre]`, `{barème}`.
  - `*(` et `*)` : ouverture et fermeture d'un groupe, avec `[options]` facultatives.
  - Toute autre ligne prolonge l'élément précédent. Une ligne vide sépare deux paragraphes ; les lignes d'un même paragraphe sont jointes par une espace.
  - Comme dans AMC, une ligne qui contient `[verbatim]` sans `[/verbatim]` ouvre un bloc brut, même si elle commence par `#`, `*` ou `+` : elle prolonge l'élément précédent, comme les lignes du bloc, jusqu'à `[/verbatim]`. L'ouverture s'écrit en minuscules ; la fermeture, en majuscules ou en minuscules.
  - Dans `[options]` et `{barème}`, une partie vide (`[ordered,]`, `{b=2,}`) est ignorée, comme dans AMC. *(vérifié dans le code d'AMC, I12)*
  - Les espaces autour d'une option sont ignorées. AMC, lui, ne reconnaît pas une option précédée d'une espace (`[horiz, ordered]`) : un tel fichier garde ici l'ordre fixe. *(dérivé, I12)*
- **Options du fichier** prises en compte : `Title`, `CompleteMulti`, `DefaultScoringS`, `DefaultScoringM`, `LaTeX`, `Disable`. Les autres options d'AMC (mise en page, copie papier, langue…) sont acceptées sans effet. Booléens : `0`, `no`, `false` et une valeur vide valent faux, comme dans AMC.
- **Options de question** : `ordered` est respectée (BAN-10). `horiz`, `columns`, `id`, `name`, `next`, `first`, `last` et `group` sont acceptées sans effet sur le déroulement (`group` donne l'étiquette, IMP-06). Une lettre `[x]` de proposition est acceptée sans effet.
- **Options de groupe** : `group` donne l'étiquette (IMP-06) ; `shuffle`, `numquestions`, `columns` et `needspace` sont acceptées sans effet.
- **Erreurs de syntaxe : le fichier est refusé** (IMP-02).
  - Fichier qui n'est pas en UTF-8 (une marque d'ordre des octets en tête est acceptée), ou qui contient un caractère nul (fichier UTF-16 ou binaire).
  - Ligne `Mot:` en début de ligne qui n'est pas une option d'AMC (« option inconnue », comme dans AMC : une ligne de texte qui commence ainsi doit être reformulée).
  - `IncludeFile:` : un fichier inclus n'est pas pris en charge, et l'ignorer ferait perdre ses questions.
  - Proposition hors d'une question ; texte avant le premier élément du fichier.
  - Question avec moins de 2 propositions ; question simple avec un nombre de bonnes réponses différent de 1.
  - Option de question ou de groupe inconnue.
  - Groupe fermé sans avoir été ouvert, ou resté ouvert à la fin du fichier ; bloc `[verbatim]` jamais fermé.
  - Titre de plus de 200 caractères ; fichier sans aucune question ; fichier de plus de 1 Mo.
- **Questions écartées : listées au récapitulatif** (IMP-03).
  - Question ouverte (`*<…>`) ou indicative (`indicative`).
  - Barème : directive autre que celles de BAR-01 (`formula`, `auto`, `set.…`, `requires.…`, `SUF`, `allowempty`, `P`…) ou valeur non numérique, dans la question, dans le barème par défaut qui s'y applique ou dans une proposition ; barème sur une proposition d'une question multiple ; sur une proposition d'une question simple, autre chose qu'une valeur seule.
  - Plus de 8 propositions, sans compter « Aucune de ces réponses n'est correcte » ; proposition de plus de 200 caractères ; énoncé ou proposition vide.
  - Limites de la base (I12) : barème de plus de 200 caractères, une fois réécrit sous sa forme courte ; étiquette de groupe de plus de 100 caractères ; valeur d'une proposition de plus de 6 chiffres avant la virgule ou de 3 après.
  - Question multiple sans bonne réponse, sans « Aucune de ces réponses n'est correcte » (`CompleteMulti: 0`).
  - Contenu converti en LaTeX léger (I17), mais refusé par celui-ci (§2 quater) : commande inconnue, formule ou accolade non fermée. Mise en forme jamais fermée.
  - Image PDF ou EPS, d'un autre format que PNG, JPEG ou SVG, ou illisible (CNT-03). Image écrite en LaTeX (`\includegraphics` avec `LaTeX: 1` ou dans `[latex]…[/latex]`) : seule `!…!` est cherchée dans l'archive. *(dérivé, I17)*
  - Doublon d'une question précédente du même fichier (IMP-07). L'étiquette de groupe n'entre pas dans la comparaison : une question répétée dans deux groupes reste un doublon.

- **Conversion du contenu (I17).** Le texte est converti en LaTeX léger (§2 quater), module par module dans l'ordre d'AMC :
  - `[verbatim]…[/verbatim]` devient un bloc de code, lignes et espaces gardés ;
  - `[latex]…[/latex]` et `[[…]]` sont gardés tels quels, comme du LaTeX ;
  - `!image.png!` devient `\includegraphics{…}` ; les options `{center}` et `[width=…]` sont acceptées sans effet ;
  - `[_…_]`, `[*…*]`, `[/…/]` et `[|…|]` deviennent italique, gras, souligné et code en ligne ; le titre `[==…==]`, du gras ;
  - le reste est du texte : `\`, `$` et les accolades y sont échappés. Avec `LaTeX: 1`, il est déjà du LaTeX et passe tel quel.
  - Le code en ligne garde ses espaces, comme un bloc (CNT-02).
  - Un module désactivé par `Disable:` laisse ses marques en texte, comme dans AMC.

## 2 quater. LaTeX léger des énoncés et des propositions (I17, *décision du commanditaire* ; détail : *dérivé*)

Hors des formules et des commandes ci-dessous, le texte s'écrit tel quel (« 50 % », « A & B », « x_1 ») : seuls `$` et `\` sont spéciaux.

- **Formules** (CNT-01) : `$…$` ou `\(…\)` en ligne ; `$$…$$` ou `\[…\]` en bloc. Leur contenu est du LaTeX de mathématiques, affiché par KaTeX.
- **Code** (CNT-02) : `\texttt{…}` ou `\verb|…|` en ligne ; `\begin{verbatim}` … `\end{verbatim}` en bloc, lignes et espaces gardés.
- **Mise en forme** (CNT-04) : `\textbf{…}` (gras), `\textit{…}` et `\emph{…}` (italique), `\underline{…}` (souligné).
- **Image** (CNT-03) : `\includegraphics{nom}` ; des options entre crochets sont acceptées sans effet. Le nom est celui donné à l'import.
- **Caractères** : `\\` est un saut de ligne ; `\$`, `\%`, `\&`, `\_`, `\#`, `\{`, `\}` et `\textbackslash{}` s'affichent tels quels. Hors d'un argument, une accolade est du texte.
- **Refusé** par le formulaire et à l'import, avec la raison : commande inconnue, formule non fermée, accolade ou crochet non fermé, argument manquant, nom d'image vide, mise en forme imbriquée sur plus de 20 niveaux.
- **Textes d'avant I17** : la migration échappe leurs `\`, `$` et accolades (`\textbackslash{}`, `\$`, `\{`, `\}`), banque et sessions comprises, comme le fait l'import (IMP-07 : une question réimportée n'est pas dupliquée). Ils s'affichent à l'identique.

## 3. Barème (logique AMC)

Calcul vérifié dans le code d'AMC (`AMC::Scoring`). Chaque question a son barème (BAR-01) : les directives de la question s'appliquent par-dessus la base `b=1`, `m=0`, `v=0`, `e=0`, `d=0`.

- **Question simple.**
  - Aucune réponse : `v`.
  - Proposition choisie qui porte sa propre valeur (BAR-01) : cette valeur.
  - Sinon : `b` si elle est juste, `m` sinon. `mz`, s'il est défini, remplace `b`. `d`, `p` et `haut` sont sans effet.
- **Question multiple.** N est le nombre de propositions, sans compter « Aucune de ces réponses n'est correcte ».
  - Aucune case cochée : `v`.
  - « Aucune… » cochée avec une autre case : `e`. Cela ne peut pas se produire : le téléphone et le serveur l'empêchent (ETU-12).
  - `haut`, s'il est défini et non nul : `d = haut − N`, et `p = 0` si `p` n'est pas défini.
  - Sinon `mz`, s'il est défini et non nul : `d = mz`, `p = 0` si `p` n'est pas défini, `b = 0` et `m = −(|mz| + |p| + 1)`. En clair : `mz` points si tout est juste, sinon `p`.
  - Note : la somme sur les N propositions de `b` pour chaque case bien traitée (juste et cochée, ou fausse et non cochée) et de `m` pour chaque case mal traitée, plus `d`. Si `p` est défini, la note ne descend pas en dessous. « Aucune… » n'entre pas dans la somme : la cocher seule laisse non cochées, donc mal traitées, les propositions justes.
  - `v` n'est ni décalé par `d` ni borné par `p` : rien coché donne exactement `v`.
- **Note maximale.** `MAX` s'il est défini ; sinon la note obtenue en cochant exactement les bonnes réponses (« Aucune… » seule, si aucune proposition n'est juste).
- **Note totale.** La somme des notes des questions. Elle n'est pas bornée et peut être négative.
- **Exemples.** Barème vide : simple, 1 si juste et 0 sinon ; multiple de 4 propositions, 1 par case bien traitée, sur 4. `haut=2`, multiple de 4 propositions : toutes justes 2, une case mal traitée 1, deux ou plus 0.
- La réponse incohérente d'une question simple (plusieurs cases) ne peut pas se produire non plus : une seule proposition se choisit.

## 4. Règles et hypothèses validées

- **Contenu figé.** Le contenu du QCM, son barème et la liste du groupe sont figés au **lancement** de la session (SES-03, décision I3 ; H8 disait « au démarrage »). Modifier la banque ou les groupes ensuite ne change ni la session ni ses résultats.
- **Questions.** En LaTeX léger depuis I17 (§2 quater) : texte, formules, code, images et mise en forme (CNT-01 à CNT-04). Avant I17, du texte brut en paragraphes.
- **Couleurs.** Six couleurs, numérotées de 1 à 6, chacune avec sa forme (AFF-03, AFF-04).
- **Correction.** Il n'y a pas de correction en classe : le professeur corrige de son côté et envoie les résultats par mail à la promotion. Aucune correction ni page de résultats n'est affichée aux étudiants ; l'export CSV (RES-02) suffit. *(confirmé par le commanditaire en I9)*
- **Retardataires.** Un étudiant arrivé après le démarrage passe sur copie AMC papier. Le QR code de jonction, affiché avant le démarrage seulement (SES-05), convient. *(confirmé en I9 ; l'application accepte toujours un retardataire qui a le code, ETU-08)*
- **Comptes enseignants.** Un espace commun à tous les comptes, créés en ligne de commande (`createsuperuser`). Pas de gestion multi-enseignants.
- **Identité de l'étudiant.** Elle est gardée par un cookie de session. Un autre appareil qui se présente avec le même numéro est refusé (ETU-02). *(I14 : l'étudiant est désigné par son n° de liste ; un autre appareil ne peut plus choisir son nom, ETU-13)*
- **Incident d'appareil.** Après le démarrage, il n'y a pas de recours dans l'application : par exemple, un téléphone tombé en panne ne peut pas être remplacé. L'enseignant garde à portée de main des copies papier d'Auto Multiple Choice. Avant le démarrage, il peut libérer un numéro (SES-04).

## 5. Points d'attention connus (non traités sauf décision contraire)

- **Usurpation.** Un étudiant qui connaît le numéro d'un camarade peut se connecter à sa place. *(I14 : il lui suffit désormais de choisir le nom d'un camarade dans la liste, sans rien connaître ; la parade reste la même)* La parade actuelle : l'enseignant voit au tableau la liste des noms connectés avant le départ (SES-02). En cas de doute, il passe aux copies papier.
- **Réservation de numéros par script.** Quelqu'un qui connaît le code de session peut essayer automatiquement les numéros du groupe et les réserver avant les vrais étudiants. *(I14 : la liste des noms et des n° est montrée à qui a le code ; un script peut donc réserver tout le groupe sans rien deviner)* Le recours retenu (SES-04) : l'enseignant voit la liste des connectés au tableau et libère les numéros usurpés avant le démarrage.
- **Données personnelles (RGPD).** Les numéros, noms et notes ne sont jamais versionnés : `.gitignore` exclut la base et les CSV, et les données de test sont fictives. La durée de conservation reste à définir avec le professeur.
- **Lecteurs de QR code à navigateur intégré.** L'identité de l'étudiant vit dans le cookie du navigateur qui a validé le numéro *(I14 : confirmé le nom)*. Une application qui ouvre le lien dans son propre navigateur peut perdre ce cookie à la fermeture : le numéro reste alors lié à ce premier « appareil » (ETU-02) et, après le démarrage, il n'y a pas de recours (§4). Non observé : à vérifier avec de vrais téléphones, l'appareil photo du téléphone ouvrant en principe le navigateur habituel.
- **Wi-Fi d'école : le risque principal avant un premier cours.** En classe, le PC et tous les téléphones seront sur **eduroam**, en mode local : les téléphones joindront le PC par son adresse sur ce réseau (de la forme `172.x.x.x`). Rien de cela n'est encore testé :
  - on ne sait pas si eduroam isole les appareils entre eux à l'INSA, ce qui empêcherait les téléphones de joindre le PC ;
  - on ne sait pas si la détection automatique de l'adresse (CLA-01) choisit celle d'eduroam. Sinon, l'enseignant la choisit sur la page « Réseau » (CLA-02). Le test du téléphone (CLA-04) dit, avant le cours, si les téléphones joignent le PC.

  Le parcours complet a réussi avec un vrai téléphone sur un Wi-Fi domestique, serveur lancé depuis Windows (hors WSL). L'hébergement sur un serveur, qui lèverait le risque d'isolation, est reporté. *(précisions du commanditaire, I9)*
- **Essai avec un vrai fichier du professeur : nécessaire avant un usage en classe.** L'import AMC a été construit sans aucun fichier réel, d'après la documentation d'AMC et son code source, et vérifié seulement sur des fichiers écrits pour les tests. Un vrai fichier peut employer des tournures non prévues : avant le premier cours, importer au moins un ancien fichier du professeur, relire le récapitulatif (questions écartées, textes ignorés) et comparer quelques notes avec celles d'AMC. *(demande du commanditaire)*
- **Partage de connexion sous Windows (après I12).** Lors d'un essai du commanditaire, le mode classe a annoncé 127.0.0.1. La cause n'a pas été reproduite : aucun Windows n'est disponible ici. Depuis I13, toutes les adresses du PC sont listées, et l'enseignant choisit la bonne (CLA-02). *(constat du commanditaire)*
  - Après I13, sur un PC Windows relié au partage de connexion d'un téléphone, l'adresse a été trouvée seule, et une session de démonstration a été jouée jusqu'au bout, installation par `install.ps1` et lancement par le raccourci compris. Le PC qui partage lui-même sa connexion reste à essayer sous Windows. *(constat du commanditaire, I13)*
- **Horloge du PC.** Sous Windows, le compte à rebours est resté stable : le recul de l'horloge observé en développement venait de WSL (REX, section R). *(constat du commanditaire, I9, que je n'ai pas observé moi-même)*

## 5 bis. Questions ouvertes, en attente du professeur

Rien de ce qui suit n'est implémenté.

*(Après I11, l'import AMC, la composition des QCM, le contenu des énoncés et le barème des questions multiples ont été tranchés par le commanditaire : voir IMP, CMP, VER, CNT, BAR-01 et §3.)*

- **Refonte de l'espace enseignant (I19, reportée, la première à sauter si le temps manque).** Elle reprendra après l'import AMC et la composition des QCM (I12 à I18), qui en changent le contenu : import, QCM repris d'anciens QCM, versions des questions, questions déjà posées à un groupe. *(décision du commanditaire, I10 ; renumérotée après I11, puis après I12)*
  - La recherche et les filtres de la banque de questions seront revus à ce moment-là. En plus de ceux proposés (texte, type, utilisation, tri, pagination), il faudra un filtre par QCM d'origine (fichier AMC importé) et un filtre « déjà posée à tel groupe ».
  - L'envoi d'une image depuis le formulaire d'une question y entrera (CNT-03). *(décision du commanditaire, I17)*
  - D'ici là, l'espace enseignant prend la police et les couleurs du socle (I10), sans changer de mise en page.
- *(Résolu en I15 par les versions précédentes, VER-03.)* **Lettres du CSV après modification d'une question** (`/code-review`, I9). Les lettres du CSV désignent les propositions figées au lancement (SES-03). Si l'enseignant modifie ensuite la question, par exemple en changeant l'ordre de ses propositions, la banque montre le nouvel ordre, et plus aucune page ne montre celui de la session. Faut-il rappeler, sur la page des résultats (réservée à l'enseignant, jamais projetée), les propositions figées de chaque question ? Aujourd'hui, AFF-01 exclut énoncés et propositions de cette page.

## 6. Journal des décisions du commanditaire

| Question | Réponse |
|---|---|
| Plusieurs questions à l'écran, une couleur par téléphone | Groupes de N et rotation synchronisée |
| Nombre de bonnes réponses | Au choix par question : simple ou multiple |
| Barème | Logique AMC, sous-ensemble b, m, v, p |
| Contenu du QR code | Identifiant, questions et réponses données *(retiré en I8)* |
| Format réutilisable | Banque de questions web |
| Qui voit la note | L'enseignant : tableau de fin et export CSV |
| Identification | Numéro pris dans une liste fournie : groupes importés en CSV |
| Hébergement | Local d'abord ; en ligne à discuter avec le professeur |
| Changer de réponse | Oui, jusqu'à la fin du temps |
| Retardataires | Acceptés |
| Repère en plus de la couleur | Oui : numéro de couleur |
| Ordre des propositions | Mélangé sur chaque téléphone |
| Hypothèses H1–H9 du plan | Validées avec le plan |
| Que peut faire l'enseignant après la création (I1) | Créer, modifier et supprimer, questions comme QCM |
| Le plancher `p` s'applique-t-il à `v` (I1) | Non : `p` ne borne que la somme des cases |
| Que peut faire l'enseignant sur un groupe (I2) | Importer, consulter, supprimer ; pour corriger, supprimer puis réimporter |
| Format du numéro d'étudiant (I2) | Chiffres uniquement (pavé numérique sur le téléphone) |
| Recours si le numéro est déjà pris (I3) | Aucun dans l'application : copies papier d'AMC en cas d'incident |
| Liste des connectés au tableau (I3) | Noms seulement, avec le décompte |
| Moment où le contenu est figé (I3) | Au lancement de la session |
| Confirmation sur le téléphone (I3) | Le nom de l'étudiant |
| Délai du « direct » au tableau (I3) | 2 secondes au plus (SES-02), confirmé |
| Recours contre la réservation de numéros (avant I4) | L'enseignant libère un numéro avant le démarrage (SES-04) |
| Revenir à « pas de réponse » sur une question simple (I4) | Oui : bouton « Effacer ma réponse » (ETU-09, livré en I5) |
| Référence d'une question dans le QR code et le CSV (I6) | Son rang dans le QCM (Q1 à Qn) *(QR code retiré en I8 ; reste le CSV)* |
| Où et quand l'enseignant voit les notes (I6) | Page non projetée, une fois la session terminée |
| Étudiants jamais connectés (I6) | Listés « Absent », sans note |
| Format du CSV des résultats (I6) | Excel en français : « ; », virgule décimale, UTF-8 avec BOM |
| Zéros de tête des numéros, perdus par Excel à l'ouverture du CSV (I6) | Numéro écrit tel quel ; colonne à reformater en texte au besoin |
| Lancement en classe (I7) | Aucune question fonctionnelle : décisions dérivées sous CLA-01 *(réservation de l'espace enseignant validée après I7, voir ci-dessous)* |
| Espace enseignant réservé au PC en mode classe (après I7) | Oui, de façon définitive |
| QR code des réponses en fin de session, FIN-01 (après I7) | Retiré, avec l'accord du professeur : son but n'avait jamais été établi |
| Rejoindre sans taper l'adresse ni le code (après I7) | QR code au tableau (SES-05) |
| QR code de jonction pendant le déroulement (I8) | Non : avant le démarrage seulement |
| Contenu du tableau et du téléphone (après I7) | Tableau : énoncés seuls. Téléphone : propositions seules. Une photo ne doit jamais contenir une question et ses réponses (AFF-01) |
| Nombre de questions affichées à la fois (après I7) | 4 par défaut, modifiable au lancement, de 1 à 6 (SES-06) |
| Correction en classe (I9) | Aucune : le professeur corrige et envoie les résultats par mail ; l'export CSV suffit |
| Ordre des propositions (I9) | Propre à chaque étudiant, stable, notes indépendantes de l'ordre (ETU-05) ; tirage au hasard conservé |
| Indication des questions à réponses multiples (I9) | « Plusieurs réponses possibles » sous l'énoncé, au tableau (AFF-02) |
| Daltonisme (I9) | Un seul affichage pour tous ; une forme par couleur (AFF-03) ; palette d'Okabe et Ito (AFF-04) |
| Horloge du PC de classe (I9) | Stable sous Windows ; le recul venait de WSL |
| Retardataires (I9) | Copie AMC papier ; QR code avant le démarrage seulement, confirmé |
| Réseau en classe (I9) | eduroam, en local, adresse en 172.x.x.x ; non testé, risque principal ; hébergement reporté |
| Import AMC et composition des QCM (I9) | Prochain incrément, en attente d'un fichier d'exemple |
| Direction visuelle (après I9) | B, « Signalétique » ; énoncés en graisse normale si le gras les alourdit (VIS-01) |
| Ordre de la refonte (après I9) | Socle et tableau (I10), puis téléphone (I11) ; espace enseignant (I12, renuméroté I16, puis I19) après l'import AMC |
| Formules, code et images (après I9) | Styles prêts seulement ; le contenu viendra avec l'import AMC |
| Recherche et filtres de la banque (après I9) | À revoir en I12 (renuméroté I16, puis I19), avec un filtre par QCM d'origine et un filtre « déjà posée à tel groupe » |
| Réseau lent sur le téléphone (après I9) | Renvoi automatique pendant le créneau ; une réponse arrivée après la fin de son créneau est signalée comme non enregistrée, jamais comme enregistrée (I11) |
| Ajouts au tableau et au téléphone (après I9) | « Questions 5–8 sur 24 » et barre du temps restant au tableau ; numéro à côté du nom et barre du temps restant sur le téléphone |
| Message de fin sur le téléphone (après I9) | « Vos réponses ont été transmises à l'enseignant » seulement si toutes ont été confirmées par le serveur ; sinon, le nombre de réponses non transmises et l'invitation à le signaler (FIN-02, I11) |
| Téléphone rechargé avec un envoi en attente (I11) | Il réaffiche ce dernier choix et continue de l'envoyer, plutôt que la réponse enregistrée (ETU-10) |
| Import AMC et composition (après I11) | AMC-TXT d'abord, puis LaTeX (sous-ensemble) ; import strict ; un parcours complet vaut mieux qu'un import exhaustif ; découpage I12 à I16 validé |
| Barème (après I11) | Celui des fichiers, sinon le défaut d'AMC ; porté par la question ; le formulaire de barème du QCM disparaît (BAR-01) |
| Erreur dans un fichier importé (après I11) | Erreur de syntaxe : fichier refusé (ligne, raison). Question valide mais non prise en charge : écartée et listée avant confirmation (IMP-02, IMP-03) |
| « Aucune de ces réponses n'est correcte » (après I11) | Reproduite : en dernier, exclusive, comptée comme une réponse (BAN-09, ETU-12) |
| Option `ordered` d'AMC (après I11) | Respectée : propositions non mélangées (BAN-10) |
| Questions identiques, fichier réimporté (après I11) | Stockées une fois et partagées ; réimport refusé avec le nom du QCM existant (IMP-07) |
| Groupes AMC avec tirage (après I11) | Toutes les questions, dans l'ordre du fichier ; nom du groupe gardé comme étiquette (IMP-06) |
| Images (après I11) | Archive ZIP ou fichier seul ; PNG, JPEG, SVG ; PDF et EPS refusés (I14, renuméroté I17) |
| Contenu (I17) | Formules, code et images sans Internet ; texte du formulaire en LaTeX léger, seuls `$` et `\` spéciaux ; image PDF ou EPS : question écartée ; mise en forme livrée en I17 (CNT-04) ; image par l'import seulement, envoi depuis le formulaire en I19 |
| Questions à la suite d'I16 (I17) | Groupe supprimé puis réimporté : la règle est gardée ; question posée dans une session lancée : masquée, plus supprimée ; listes des QCM triées par titre |
| Nombre de propositions (après I11) | 8 au plus, sans compter « Aucune… » |
| Questions déjà posées (après I11) | Signalées, l'enseignant décide ; historique lié au groupe et à son année, pas au seul nom (CMP-03, GRP-04 proposé) |
| Modifier une question déjà utilisée (après I11) | Nouvelle version ; elle remplace l'ancienne dans les QCM, jamais dans les sessions ; liste des QCM touchés, avec la possibilité de limiter au QCM courant (VER-01, VER-02) |
| Démonstration (après I11) | Fichier AMC-TXT fictif dans le dépôt, `make demo`, section « Premier cours » du README (DEM-01, DEM-02) |
| Découpage après I12 | I13 lancement en classe, sauvegarde et Note /20 ; I14 identification par la liste du groupe ; I15 composition et réimport ; I16 séance (terminer le créneau, « déjà posée », année du groupe) ; I17 formules, code, images ; I18 LaTeX AMC (mis de côté en D, à confirmer) ; I19 espace enseignant, le premier à sauter si le temps manque |
| Démonstration complète (après I17) | Incrément D : commande à part, `qcm-live demo`, sur une base séparée recréée à chaque lancement ; l'installation garde la démonstration légère ; trois fichiers, deux groupes « L1 Sciences », une session passée, un QCM composé, une nouvelle version, parcours de 10 minutes dans GUIDE.md ; formules en rouge expliquées dans le guide (DEM-03 à DEM-08, CNT-05) |
| PC de classe (après I12) | PC personnel de l'enseignant sous Linux, droits administrateur et Internet à l'installation ; Windows doit fonctionner, en second |
| Installation et lancement (après I12) | Une ligne curl, sans make ni git ni sudo ; commande `qcm-live` et icône au menu ; le lancement est toujours le mode classe et ouvre le navigateur ; démonstration proposée à l'installation ; relancer la ligne met à jour sans toucher aux données ; guide de l'enseignant à part (INS-01 à INS-03) |
| Adresse du PC (après I12) | Partage de connexion dans les deux sens ; adresses candidates au terminal et au tableau, choix sans redémarrer (CLA-02) |
| Pare-feu (après I12) | Détecté et signalé avec la commande, jamais ouvert par l'application ; test avec un téléphone (CLA-03, CLA-04) |
| Sauvegarde (après I12) | À chaque lancement, 10 gardées, dans le répertoire personnel ; commandes sauvegarder et restaurer (SAV-01, SAV-02) |
| Note sur 20 (après I12) | Total ÷ maximum × 20, au centième le plus proche, bornée entre 0 et 20 ; vide pour un absent ou un maximum ≤ 0 ; colonne après `note max` (RES-03) |
| Écran dupliqué (après I12) | Résultats ouverts notes masquées (RES-04, I13) ; « Gérer les connectés » inchangée |
| Terminer le créneau en cours (après I12, I16) | Le clic ramène le temps restant à 5 s ; clic en deux temps (« Confirmer » pendant 3 s) ; rattrapage par +10 s ; sur le dernier créneau, la session se termine ; « k / n ont répondu » au tableau (révision de DER-02 et DER-03) |
| Identification (après I12, I14) | Numéro de liste du groupe, stable, comme identifiant interne ; l'étudiant choisit son nom dans la liste, avec une recherche, puis confirme ; aucun numéro à saisir ni projeté ; 70 étudiants au plus ; fichier à en-tête (`n°`, `numéro étudiant`, `nom`), ancien format accepté ; CSV : `n°`, `numéro étudiant`, `nom`, notes ; migrations des groupes et sessions existants validées |
| Identification, précisions (I14) | Numéro étudiant facultatif, texte libre (≤ 20 caractères, unique s'il est rempli) ; n° entier de 1 à 999, unique, trous permis, n'importe quel ordre (ancien format : rang dans le fichier) ; sur le téléphone, noms pris grisés « déjà connecté », non sélectionnables ; le téléphone montre le n° de liste, jamais le numéro étudiant (GRP-05, ETU-13, RES-05, MIG-01) |
| « Déjà posée » (après I12, I16) | Calculé par étudiant (numéro étudiant, sinon nom exact) : « posée à 12 étudiants sur 80 » |
| Séance, précisions (I16) | Année du groupe validée, format « AAAA-AAAA » contrôlé ; groupes et sessions existants datés d'après leurs sessions (MIG-02) ; « déjà posée » : étudiant identifié dans une session démarrée, même nom de groupe et même année ; n de « k / n ont répondu » : les connectés ; dernier créneau terminé : fin après 5 s (GRP-04, CMP-03, DER-04, TPS-02) |
| Réimport d'un fichier AMC (après I12, I15) | Permis ; question reconnue par son origine (fichier, rang) ; modification de l'enseignant gardée ; questions manquantes recréées et remises ; récapitulatif « déjà là, ajoutée, écartée » ; fichier corrigé : nouveau QCM ; « retirer du QCM » distinct de « supprimer de la banque » *(remplacera le refus d'IMP-07)* |
| Ordre et composition (après I12, I15) | Cases à cocher ; une question remise retrouve sa place dans le fichier, les autres à la suite ; plus de saisie de rang |
| Versions et réimport, précisions (I15) | Ancienne version masquée de la banque, consultable depuis la nouvelle ; « utilisée » dès le lancement ; question jamais utilisée modifiée sur place partout ; fichier d'avant I15 reconnu par identité puis par place libre (VER-01, VER-03, IMP-10) |
