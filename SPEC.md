# SPEC — QCM Live

Spécification fonctionnelle de référence : la spec initiale enrichie des réponses de la commanditaire.

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
  - le nombre N de questions affichées en même temps, de 1 à 6 (1 par défaut) ;
  - le temps t par question, de 5 à 600 secondes (30 par défaut).

  Un identifiant de session de 6 chiffres est généré, distinct de ceux des autres sessions. Les sessions lancées sont listées dans l'espace enseignant. *(liste : dérivé)*
- **[SES-02]** (I3) Avant le départ, le tableau affiche :
  - l'adresse à ouvrir et l'identifiant de session ;
  - le QCM et le groupe ;
  - les **noms** des étudiants connectés, sans leur numéro, avec le décompte « k / n connectés ». La liste se met à jour en direct.

  L'enseignant clique sur « Démarrer ». *(dérivé)*
- **[SES-03]** (I3) Le QCM et la liste du groupe sont **figés au lancement**. Modifier ou supprimer ensuite le QCM, ses questions ou le groupe ne change pas la session.
- **[ETU-01]** (I3) L'étudiant ouvre l'application sur son téléphone, à l'adresse projetée. Il saisit l'identifiant de session, puis son numéro d'étudiant, sur le pavé numérique. Son téléphone affiche alors son nom, pour confirmer son identité.
- **[ETU-02]** (I3) Un identifiant de session inconnu est refusé. Un numéro absent du groupe de la session est refusé. Un numéro déjà utilisé dans la session, depuis un autre appareil, est refusé : il reste lié à ce premier appareil jusqu'à la fin de la session, sans recours dans l'application.
- **[ETU-03]** (I3) Un téléphone rechargé ou sorti de veille retrouve l'identité de l'étudiant, sans nouvelle saisie. Ressaisir l'identifiant de la session mène aussi directement à son écran.

### Session : déroulement
- **[DER-01]** (I4) Après le démarrage, les questions défilent **par groupes de N**, dans l'ordre du QCM ; le dernier groupe peut en compter moins. Au tableau, chaque question du groupe affiche son énoncé et ses propositions (A, B, C…) sur sa **couleur de fond** avec son **numéro de couleur**.
- **[DER-02]** (I4) Un groupe de n questions se déroule en n **créneaux** synchronisés de t secondes, identiques pour tous. À la fin du temps, on passe automatiquement au créneau suivant. Il n'y a ni pause ni saut. Le temps restant s'affiche au tableau et sur les téléphones.
- **[ETU-04]** (I4) Pendant un créneau, le fond du téléphone prend la couleur de la question à laquelle l'étudiant doit répondre, avec son numéro de couleur. Seules les propositions s'affichent, **jamais l'énoncé**.
- **[ETU-05]** (I4) Sur chaque téléphone, les propositions sont mélangées. L'ordre est propre à l'étudiant et reste stable pour une question donnée.
- **[ETU-06]** (I4) Tous les étudiants répondent à toutes les questions, mais pas dans le même ordre : à chaque créneau d'un groupe, chacun a une autre question du groupe (rotation). Si N=1, l'ordre est forcément le même pour tous.
- **[ETU-07]** (I4) L'étudiant peut changer sa réponse jusqu'à la fin du créneau ; c'est la dernière qui compte. Après la fin du créneau, toute réponse est refusée.
- **[ETU-08]** (I4) Un étudiant peut rejoindre une session déjà commencée. Les créneaux qu'il a manqués comptent comme non-réponse.
- **[DER-03]** (I4) Le tableau n'affiche ni la correction ni de statistiques pendant la session.

### Session : temps additionnel
- **[TPS-01]** (I5) Pendant un créneau, l'enseignant peut ajouter 10 secondes depuis son PC. Le temps restant augmente de 10 s au tableau et sur tous les téléphones, et les créneaux suivants sont décalés d'autant. Les ajouts se cumulent. Une réponse envoyée pendant le temps ajouté est acceptée.

### Fin de session et résultats
- **[FIN-01]** (I6) À la fin de la session, chaque téléphone affiche un QR code. Il contient le code de session, le numéro de l'étudiant et, pour chaque question dans l'ordre où il l'a eue, la référence de la question et la réponse donnée. Les lettres sont celles du tableau, et `-` signifie aucune réponse.
- **[RES-01]** (I6) L'enseignant voit le tableau des résultats de la session : numéro, nom, note et note maximale. La note suit le barème AMC du QCM (§3).
- **[RES-02]** (I6) L'enseignant télécharge les résultats en CSV : une ligne par étudiant, avec la note et, pour chaque question, la réponse donnée et les points obtenus.

### Mode classe
- **[CLA-01]** (I7) L'application se lance en mode classe sur le PC de l'enseignant : serveur de production local, sans mode debug. Elle fonctionne de bout en bout depuis les téléphones du réseau local, et l'adresse à ouvrir s'affiche.

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
- **Couleurs.** Six couleurs contrastées, numérotées de 1 à 6.
- **Comptes enseignants.** Un espace commun à tous les comptes, créés en ligne de commande (`createsuperuser`). Pas de gestion multi-enseignants.
- **Identité de l'étudiant.** Elle est gardée par un cookie de session. Un autre appareil qui se présente avec le même numéro est refusé (ETU-02).
- **Incident d'appareil.** Il n'y a pas de recours dans l'application : par exemple, un téléphone tombé en panne ne peut pas être remplacé en cours de session. L'enseignant garde à portée de main des copies papier d'Auto Multiple Choice.

## 5. Points d'attention connus (non traités sauf décision contraire)

- **Usurpation.** Un étudiant qui connaît le numéro d'un camarade peut se connecter à sa place. La parade actuelle : l'enseignant voit au tableau la liste des noms connectés avant le départ (SES-02). En cas de doute, il passe aux copies papier.
- **Données personnelles (RGPD).** Les numéros, noms et notes ne sont jamais versionnés : `.gitignore` exclut la base et les CSV, et les données de test sont fictives. La durée de conservation reste à définir avec le professeur.
- **Wi-Fi d'école.** L'isolation entre appareils peut empêcher les téléphones de joindre le PC de l'enseignant. Dans ce cas, l'hébergement en ligne (incrément conditionnel I8) devient nécessaire.

## 6. Journal des décisions de la commanditaire

| Question | Réponse |
|---|---|
| Plusieurs questions à l'écran, une couleur par téléphone | Groupes de N et rotation synchronisée |
| Nombre de bonnes réponses | Au choix par question : simple ou multiple |
| Barème | Logique AMC, sous-ensemble b, m, v, p |
| Contenu du QR code | Identifiant, questions et réponses données |
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
