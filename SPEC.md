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
- **[BAN-02]** (I1) L'enseignant crée une question **multiple** : un énoncé et 2 à 8 propositions, dont au moins une juste.
- **[BAN-03]** (I1) L'enseignant crée un QCM : un titre et une sélection **ordonnée** d'au moins une question de la banque. Un QCM sans question ne peut pas se lancer. Il peut le devenir après la suppression de ses questions (BAN-07) ; pour le modifier, il faut alors lui redonner au moins une question.
- **[BAN-04]** (I1) Une même question de la banque peut servir dans plusieurs QCM.
- **[BAN-05]** (I1) L'enseignant modifie une question : énoncé, type, propositions, bonnes réponses. Les règles de validité sont les mêmes qu'à la création.
- **[BAN-06]** (I1) L'enseignant modifie un QCM : titre, questions, ordre, barème.
- **[BAN-07]** (I1) L'enseignant supprime une question après confirmation. La page de confirmation nomme les QCM qui l'utilisent. La question est retirée de ces QCM.
- **[BAN-08]** (I1) L'enseignant supprime un QCM après confirmation. Ses questions restent dans la banque.
- **[BAR-01]** (I1) Chaque QCM porte son barème, sur le modèle d'Auto Multiple Choice (AMC). Il a deux échelles :
  - questions simples : `b` (juste), `m` (faux), `v` (pas de réponse) ;
  - questions multiples : `b` (par case bien traitée), `m` (par case mal traitée), `v` (aucune case cochée), `p` (plancher de la note de la question ; vide = pas de plancher).

  Valeurs par défaut : `b=1`, `m=0`, `v=0`, `p` vide. Les valeurs peuvent être négatives.

### Enseignant : groupes d'étudiants
- **[GRP-01]** (I2) L'enseignant importe un groupe d'étudiants : il donne au groupe un nom unique et fournit un fichier CSV (numéro, nom). Le groupe et ses étudiants s'affichent. Les numéros gardent leurs éventuels zéros de tête.
- **[GRP-02]** (I2) Un CSV invalide est refusé en entier, sans rien créer. Le message désigne chaque ligne fautive (les 20 premières, puis le nombre des autres) : format incorrect, numéro en double, numéro ou nom vide, numéro qui ne contient pas que des chiffres. Un fichier sans étudiant est refusé, de même qu'un nom de groupe vide ou déjà pris.
- **[GRP-03]** (I2) L'enseignant supprime un groupe après confirmation. Pour corriger une liste, il supprime le groupe puis le réimporte.

### Session : lancement et accueil
- **[SES-01]** (I3) L'enseignant lance une session. Il choisit :
  - un QCM, parmi ceux qui ont au moins une question ;
  - un groupe ;
  - le nombre N de questions affichées en même temps, de 1 à 6 (SES-06) ;
  - le temps t par question, de 5 à 600 secondes (30 par défaut).

  Un identifiant de session de 6 chiffres est généré, distinct de ceux des autres sessions. Les sessions lancées sont listées dans l'espace enseignant. *(liste : dérivé)*
- **[SES-06]** (I9) Par défaut, 4 questions s'affichent à la fois. L'enseignant peut choisir une autre valeur au lancement, de 1 à 6 ; elle reste fixe pendant toute la session. *(précision du commanditaire)*
  - Le tableau tient sans défilement en 1920x1080 et en 1280x720 avec 4 énoncés d'environ 200 caractères, ou 6 d'environ 135 (trois colonnes à partir de 5). Au-delà, ou sur un écran plus petit (1024x768), il peut défiler. *(dérivé, I9)*
- **[SES-02]** (I3) Avant le départ, le tableau affiche :
  - l'adresse à ouvrir et l'identifiant de session ;
  - le QCM et le groupe ;
  - les **noms** des étudiants connectés, sans leur numéro, avec le décompte « k / n connectés ». La liste se met à jour en direct, en 2 secondes au plus, sans recharger la page.

  L'enseignant clique sur « Démarrer ». *(dérivé)*
- **[SES-05]** (I8) Avant le départ, le tableau affiche aussi un **QR code pour rejoindre la session**, pour que l'étudiant n'ait à taper ni l'adresse ni le code. Le lire ouvre directement l'écran de cette session sur le téléphone, où il ne reste à saisir que le numéro d'étudiant (ETU-01).
  - L'adresse et le code restent affichés en texte, pour un téléphone qui ne lit pas le QR code. *(dérivé)*
  - Le QR code disparaît au démarrage. *(décision I8)* Le tableau en déroulement n'affiche ni le QR code ni l'adresse, seulement le code de session dans son titre : un retardataire (ETU-08) doit obtenir l'adresse autrement, auprès d'un camarade ou de l'enseignant. *(conséquence acceptée, décision I8)*
  - En mode classe, il contient l'adresse du PC sur le réseau local (CLA-01), même si le tableau est ouvert en `localhost`. *(dérivé)*
  - Un téléphone déjà identifié qui le lit retrouve son écran, sans nouvelle saisie (ETU-03). *(dérivé)*
- **[SES-03]** (I3) Le QCM et la liste du groupe sont **figés au lancement**. Modifier ou supprimer ensuite le QCM, ses questions ou le groupe ne change pas la session.
- **[ETU-01]** (I3) L'étudiant ouvre l'application sur son téléphone, à l'adresse projetée. Il saisit l'identifiant de session, puis son numéro d'étudiant, sur le pavé numérique. Son téléphone affiche alors son nom, pour confirmer son identité.
- **[ETU-02]** (I3) Un identifiant de session inconnu est refusé. Un numéro absent du groupe de la session est refusé. Un numéro déjà utilisé dans la session, depuis un autre appareil, est refusé : il reste lié à ce premier appareil, sauf si l'enseignant le libère avant le démarrage (SES-04).
- **[SES-04]** (I4) Avant le démarrage, l'enseignant peut **libérer un numéro**. Il le fait depuis une page de gestion des connectés, ouverte depuis le tableau mais non projetée, qui montre les numéros et les noms. L'appareil qui occupait le numéro perd son identité, et le vrai étudiant peut alors le saisir. Après le démarrage, aucune libération n'est possible.
- **[ETU-03]** (I3) Un téléphone rechargé ou sorti de veille retrouve l'identité de l'étudiant, sans nouvelle saisie. Ressaisir l'identifiant de la session mène aussi directement à son écran.

### Session : déroulement
- **[DER-01]** (I4) Après le démarrage, les questions défilent **par groupes de N**, dans l'ordre du QCM ; le dernier groupe peut en compter moins. Au tableau, chaque question du groupe affiche, sur sa **couleur de fond** et avec son **numéro de couleur** (1 à N) et sa forme (AFF-03), son énoncé seul (AFF-01). Le contenu affiché est celui qui a été figé au lancement (SES-03). À la fin du dernier créneau, le tableau indique que la session est terminée.
- **[DER-02]** (I4) Un groupe de n questions se déroule en n **créneaux** synchronisés de t secondes, identiques pour tous. À la fin du temps, on passe automatiquement au créneau suivant, sans recharger à la main : le tableau et les téléphones suivent en 2 secondes au plus. Il n'y a ni pause ni saut. Le temps restant s'affiche au tableau et sur les téléphones. Après le dernier créneau, les téléphones indiquent que la session est terminée.
- **[ETU-04]** (I4) Pendant un créneau, le fond du téléphone prend la couleur de la question à laquelle l'étudiant doit répondre, avec son numéro de couleur et sa forme (AFF-03). Seules les propositions s'affichent, sans lettre et **jamais l'énoncé** :
  - question simple : on en choisit une ;
  - question multiple : on coche une ou plusieurs cases.

  Chaque choix est enregistré aussitôt, sans bouton à valider, et le téléphone confirme l'enregistrement. *(enregistrement immédiat : dérivé)*
- **[ETU-05]** (I4) Sur chaque téléphone, les propositions sont mélangées. L'ordre est propre à l'étudiant et reste stable pour une question donnée. *(précisé en I9)* Il reste le même quand le téléphone recharge la page ou revient sur la session, et la note ne dépend pas de l'ordre affiché : une réponse désigne une proposition, pas sa place à l'écran.
  - L'ordre est tiré au hasard, indépendamment pour chaque étudiant. L'application ne sait pas qui est assis à côté de qui : deux étudiants qui ont la même question au même moment peuvent voir une proposition au même endroit (1 fois sur 4 avec 4 propositions). Une répartition qui l'éviterait entre étudiants connectés à la suite a été écartée, rien ne garantissant que des voisins de table se connectent l'un après l'autre. *(décision I9)*
- **[ETU-06]** (I4) Tous les étudiants répondent à toutes les questions, mais pas dans le même ordre : à chaque créneau d'un groupe, chacun a une autre question du groupe (rotation). Si N=1, l'ordre est forcément le même pour tous.
- **[ETU-07]** (I4) L'étudiant peut changer sa réponse jusqu'à la fin du créneau ; c'est la dernière qui compte. Un téléphone rechargé réaffiche la réponse enregistrée. Après la fin du créneau, toute réponse est refusée par le serveur, et le téléphone le signale.
- **[ETU-08]** (I4) Un étudiant peut rejoindre une session déjà commencée. Les créneaux qu'il a manqués comptent comme non-réponse.
- **[ETU-09]** (I5) Sur une question simple, l'étudiant peut **effacer sa réponse** jusqu'à la fin du créneau, avec le bouton « Effacer ma réponse » : plus aucune proposition n'est choisie, le téléphone confirme l'effacement et la question compte comme non-réponse (v). Sur une question multiple, décocher toutes les cases revient au même. Après la fin du créneau, l'effacement est refusé comme toute réponse (ETU-07). *(dérivé : le téléphone affiche « Réponse effacée » ; le bouton est inactif quand aucune proposition n'est choisie)*
- **[DER-03]** (I4) Le tableau n'affiche ni la correction ni de statistiques pendant la session.

- **[AFF-01]** (I9) **Une capture d'écran ou une photo ne contient jamais à la fois une question et ses réponses.** À aucun moment de la session, le tableau n'affiche ni ne reçoit une proposition de réponse, et le téléphone n'affiche ni ne reçoit un énoncé (ETU-04). Les pages des résultats et le CSV ne contiennent ni énoncé ni proposition.
  - Les pages de la banque de questions et des QCM, réservées à l'enseignant et sans rapport avec le déroulement, montrent encore l'un et l'autre, puisqu'elles servent à les rédiger. L'enseignant ne les projette pas pendant une évaluation. *(dérivé)*
- **[AFF-02]** (I9) Au tableau, une question à réponses multiples porte la mention « Plusieurs réponses possibles » sous son énoncé. Une question simple n'a aucune mention. *(forme choisie par le commanditaire : texte seul, sans le ♣ d'AMC)*
- **[AFF-03]** (I9) Chaque couleur a, en plus de son numéro, une **forme** qui lui est propre, au tableau comme sur le téléphone : 1 ● rond, 2 ▲ triangle, 3 ■ carré, 4 ◆ losange, 5 ★ étoile, 6 ✚ croix. Il n'y a qu'un affichage, lisible par tous, sans mode à activer. *(choix des formes : proposé en I9, validé)*
- **[AFF-04]** (I9) Les six couleurs sont celles de la palette d'Okabe et Ito, conçue pour rester distincte dans les principaux types de daltonisme, dans cet ordre : 1 jaune `#F0E442`, 2 bleu `#0072B2`, 3 vert bleuté `#009E73`, 4 bleu ciel `#56B4E9`, 5 pourpre `#CC79A7`, 6 orange `#E69F00`. Tout texte affiché sur une couleur, au tableau comme sur le téléphone, a un contraste d'au moins 4,5:1 (texte blanc sur le bleu). *(décision I9)*
  - Ordre choisi pour N = 4, la valeur par défaut : les 4 premières couleurs restent distinctes en vision normale, en protanopie, deutéranopie et tritanopie simulées, sur un projecteur délavé, et même en niveaux de gris. Au-delà de 4, la forme et le numéro départagent les couleurs que la simulation rapproche. *(décision I9, mesures dans REX.md)*
  - L'ancienne palette confondait le jaune et l'orange (1 et 5) en deutéranopie et sur projecteur, le bleu et le violet (2 et 6) en protanopie, et ses six couleurs avaient presque la même luminosité. *(constat I9)*

### Session : temps additionnel
- **[TPS-01]** (I5) Pendant un créneau, l'enseignant peut ajouter 10 secondes depuis son PC. Le temps restant augmente de 10 s au tableau et sur tous les téléphones, et les créneaux suivants sont décalés d'autant. Les ajouts se cumulent. Une réponse envoyée pendant le temps ajouté est acceptée. Le bouton « +10 s » est sur le tableau, pendant le déroulement seulement ; un clic arrivé après la fin du créneau n'ajoute rien. *(emplacement et clic tardif : dérivé)*

### Fin de session et résultats
- *FIN-01 (livrée en I6, retirée en I8).* Le QR code des réponses, affiché en fin de session sur le téléphone, est retiré avec l'accord du professeur : son but n'avait jamais été établi. L'identifiant n'est pas réattribué.
- **[FIN-02]** (I8) À la fin de la session, le téléphone indique seulement que la session est terminée : ni QR code, ni réponses, ni note.
- **[RES-01]** (I6) L'enseignant voit le tableau des résultats de la session : numéro, nom, note et note maximale. La note suit le barème AMC du QCM (§3).
  - Les résultats sont sur une **page non projetée**, disponible une fois la session terminée. On l'ouvre depuis le tableau ou depuis la liste des sessions, qui indique l'état de chaque session (en attente, en cours, terminée). Avant la fin, la page n'affiche ni étudiant ni note. *(décision I6)*
  - Le lien « Résultats » n'apparaît, au tableau comme dans la liste des sessions, qu'une fois la session terminée. *(dérivé)*
  - Tous les étudiants du groupe figé sont listés, dans l'ordre du fichier importé. Ceux qui ne se sont jamais connectés sont marqués **« Absent »**, sans note. Un étudiant connecté qui n'a rien répondu n'est pas absent : chaque question lui vaut v. *(décision I6)*
  - Les nombres s'écrivent à la française, sans zéro inutile (1,75 ; 3 ; -0,5). *(dérivé)*
- **[RES-02]** (I6) L'enseignant télécharge les résultats en CSV : une ligne par étudiant, avec la note et, pour chaque question, la réponse donnée et les points obtenus.
  - Format d'Excel en français : séparateur point-virgule, virgule décimale, UTF-8 avec BOM. Fichier `resultats-<code>.csv`. *(décision I6)*
  - Le CSV n'est téléchargeable qu'une fois la session terminée. *(dérivé)*
  - Le numéro est écrit tel quel. Excel, à l'ouverture, en retire les zéros de tête : on peut reformater la colonne en texte. *(décision I6)*
  - Colonnes : `numéro`, `nom`, `note`, `note max`, puis, pour chaque question dans l'ordre du QCM, `Qn réponse` et `Qn points`. Une réponse s'écrit avec les lettres des propositions dans l'ordre de la banque au moment du lancement (A pour la première), `-` signifie aucune réponse. *(précisé en I9 : le tableau n'affiche plus ces lettres)* Tant que la question n'a pas été modifiée, ce sont les lettres de la liste des questions. Après une modification (BAN-05), plus aucune page ne montre l'ordre figé : voir §5 bis. *(constat I9)* Un absent a `Absent` pour note et des cellules de questions vides. *(dérivé)*
  - Un nom ou un numéro qui commence par `=`, `+`, `-`, `@`, une tabulation ou un retour chariot est précédé d'une apostrophe, pour qu'un tableur n'exécute aucune formule. Les nombres calculés (notes, points) ne le sont jamais. *(dérivé)*

### Mode classe
- **[CLA-01]** (I7) L'application se lance en mode classe sur le PC de l'enseignant : serveur de production local, sans mode debug. Elle fonctionne de bout en bout depuis les téléphones du réseau local, et l'adresse à ouvrir s'affiche.
  - Une commande : `make classe` (port 8000 par défaut). Le mode debug est toujours désactivé, quel que soit le réglage de `.env`. *(dérivé)*
  - L'adresse à ouvrir sur les téléphones est celle du PC sur le réseau local (par exemple `http://192.168.1.23:8000/`). Elle s'affiche dans le terminal, avec celle de l'espace enseignant, et le tableau la projette (SES-02) même s'il est ouvert en `localhost`. *(dérivé)*
  - Si la détection choisit la mauvaise interface réseau, l'enseignant impose l'adresse (`ADRESSE=…`). *(dérivé)*
  - En mode classe, l'espace enseignant (connexion, notes, pilotage) ne s'ouvre que sur le PC de l'enseignant ; depuis un autre appareil, il est refusé. *(décision du commanditaire, définitive)* Les étudiants partagent le réseau du serveur, et la connexion passe en clair (HTTP). *(dérivé)*
  - Toute une classe (40 téléphones) peut valider son numéro, puis répondre, au même instant, sans qu'aucune requête échoue. *(dérivé)*
  - Hors mode debug, les pages d'erreur (page introuvable, requête refusée, formulaire expiré, erreur du serveur) sont en français, comme le reste de l'interface. *(dérivé)*

## 2 bis. Format du CSV d'un groupe (*dérivé*)

- Une ligne par étudiant : numéro, puis nom (par exemple « DUPONT Jeanne »).
- **Séparateur.** Point-virgule, comme dans les exports d'Excel en français, ou virgule. On retient le point-virgule s'il apparaît dans la première ligne non vide.
- **Numéro.** De 1 à 20 chiffres de 0 à 9.
- **Nom.** De 1 à 200 caractères, sans caractère de contrôle.
- **En-tête facultatif.** La première ligne non vide est un en-tête si elle a deux colonnes remplies et si sa première ne contient aucun chiffre (par exemple « numéro;nom »). Le message de confirmation de l'import cite la ligne ainsi ignorée.
- **Tolérances.** Les lignes vides et les colonnes vides en fin de ligne sont ignorées.
- **Encodage.** UTF-8, avec ou sans BOM, ou Windows-1252 pour les anciens exports d'Excel.
- **Numéros de ligne.** Ceux des messages d'erreur sont ceux du fichier, en commençant à 1.

## 3. Barème (logique AMC, sous-ensemble b, m, v, p)

- **Question simple.**
  - Aucune réponse : `v`.
  - Proposition juste choisie : `b`.
  - Sinon : `m`.
- **Question multiple.**
  - Aucune case cochée : `v`.
  - Sinon, la note est la somme sur toutes les propositions : `b` pour chaque case bien traitée (juste et cochée, ou fausse et non cochée), `m` pour chaque case mal traitée.
  - Si `p` est renseigné, cette somme ne descend pas en dessous de `p`. Le plancher ne s'applique pas à `v` : rien coché donne exactement `v`.
- **Note maximale.** `b` pour une question simple, `b ×` le nombre de propositions pour une question multiple.
- **Note totale.** La somme des notes des questions. Elle n'est pas bornée et peut être négative.
- La réponse incohérente d'AMC (`e`) ne peut pas se produire : l'interface empêche de cocher plusieurs cases sur une question simple.

## 4. Règles et hypothèses validées

- **Contenu figé.** Le contenu du QCM, son barème et la liste du groupe sont figés au **lancement** de la session (SES-03, décision I3 ; H8 disait « au démarrage »). Modifier la banque ou les groupes ensuite ne change ni la session ni ses résultats.
- **Questions.** Texte brut, sans image ni formule.
- **Couleurs.** Six couleurs, numérotées de 1 à 6, chacune avec sa forme (AFF-03, AFF-04).
- **Correction.** Il n'y a pas de correction en classe : le professeur corrige de son côté et envoie les résultats par mail à la promotion. Aucune correction ni page de résultats n'est affichée aux étudiants ; l'export CSV (RES-02) suffit. *(confirmé par le commanditaire en I9)*
- **Retardataires.** Un étudiant arrivé après le démarrage passe sur copie AMC papier. Le QR code de jonction, affiché avant le démarrage seulement (SES-05), convient. *(confirmé en I9 ; l'application accepte toujours un retardataire qui a le code, ETU-08)*
- **Comptes enseignants.** Un espace commun à tous les comptes, créés en ligne de commande (`createsuperuser`). Pas de gestion multi-enseignants.
- **Identité de l'étudiant.** Elle est gardée par un cookie de session. Un autre appareil qui se présente avec le même numéro est refusé (ETU-02).
- **Incident d'appareil.** Après le démarrage, il n'y a pas de recours dans l'application : par exemple, un téléphone tombé en panne ne peut pas être remplacé. L'enseignant garde à portée de main des copies papier d'Auto Multiple Choice. Avant le démarrage, il peut libérer un numéro (SES-04).

## 5. Points d'attention connus (non traités sauf décision contraire)

- **Usurpation.** Un étudiant qui connaît le numéro d'un camarade peut se connecter à sa place. La parade actuelle : l'enseignant voit au tableau la liste des noms connectés avant le départ (SES-02). En cas de doute, il passe aux copies papier.
- **Réservation de numéros par script.** Quelqu'un qui connaît le code de session peut essayer automatiquement les numéros du groupe et les réserver avant les vrais étudiants. Le recours retenu (SES-04) : l'enseignant voit la liste des connectés au tableau et libère les numéros usurpés avant le démarrage.
- **Données personnelles (RGPD).** Les numéros, noms et notes ne sont jamais versionnés : `.gitignore` exclut la base et les CSV, et les données de test sont fictives. La durée de conservation reste à définir avec le professeur.
- **Lecteurs de QR code à navigateur intégré.** L'identité de l'étudiant vit dans le cookie du navigateur qui a validé le numéro. Une application qui ouvre le lien dans son propre navigateur peut perdre ce cookie à la fermeture : le numéro reste alors lié à ce premier « appareil » (ETU-02) et, après le démarrage, il n'y a pas de recours (§4). Non observé : à vérifier avec de vrais téléphones, l'appareil photo du téléphone ouvrant en principe le navigateur habituel.
- **Wi-Fi d'école : le risque principal avant un premier cours.** En classe, le PC et tous les téléphones seront sur **eduroam**, en mode local : les téléphones joindront le PC par son adresse sur ce réseau (de la forme `172.x.x.x`). Rien de cela n'est encore testé :
  - on ne sait pas si eduroam isole les appareils entre eux à l'INSA, ce qui empêcherait les téléphones de joindre le PC ;
  - on ne sait pas si la détection automatique de l'adresse (CLA-01) choisit celle d'eduroam. Sinon, l'enseignant l'impose avec `ADRESSE=…`.

  Le parcours complet a réussi avec un vrai téléphone sur un Wi-Fi domestique, serveur lancé depuis Windows (hors WSL). L'hébergement sur un serveur, qui lèverait le risque d'isolation, est reporté. *(précisions du commanditaire, I9)*
- **Horloge du PC.** Sous Windows, le compte à rebours est resté stable : le recul de l'horloge observé en développement venait de WSL (REX, section R). *(constat du commanditaire, I9, que je n'ai pas observé moi-même)*

## 5 bis. Questions ouvertes, en attente du professeur

Rien de ce qui suit n'est implémenté.

- **Import des questions depuis AMC (prochain incrément, en attente).** Les questions viennent de fichiers AMC d'anciens QCM, en texte AMC ou en LaTeX, avec formules et code. Le barème figure dans ces fichiers. *(précision du commanditaire, I9)* Aucun fichier d'exemple n'est encore disponible : rien ne sera fait sans lui.
- **Composition des QCM.** Un nouveau QCM se crée en reprenant un ancien QCM en entier, puis en ajoutant ou en retirant des questions. *(précision du commanditaire, I9)* Contrainte déjà posée : une question ne doit jamais retomber pour une même promo.
- **Contenu des énoncés.** Formules et code, issus des fichiers AMC (aujourd'hui, texte brut seulement : §4). Images : non précisé.
- **Barème exact des questions à réponses multiples** : celui des fichiers AMC (aujourd'hui, le §3).
- **Lettres du CSV après modification d'une question** (`/code-review`, I9). Les lettres du CSV désignent les propositions figées au lancement (SES-03). Si l'enseignant modifie ensuite la question, par exemple en changeant l'ordre de ses propositions, la banque montre le nouvel ordre, et plus aucune page ne montre celui de la session. Faut-il rappeler, sur la page des résultats (réservée à l'enseignant, jamais projetée), les propositions figées de chaque question ? Aujourd'hui, AFF-01 exclut énoncés et propositions de cette page.

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
