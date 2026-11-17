# R — Corrections issues d'un audit externe

## Objectif
En fin de projet, un relecteur **extérieur à mes sessions** a analysé le dépôt et mes journaux de session. Ses 7 constats portent sur ma méthode et mon environnement de travail, pas sur l'application : aucune exigence de SPEC.md ne change, et le numéro d'incrément de `pyproject.toml` reste 7. Deux retouches de l'application viennent de l'audit interne qui a suivi, sans rien changer à son fonctionnement normal : le décompte du navigateur entre deux interrogations, et la lecture de l'horloge dans `add_time` (voir plus bas). Le commanditaire m'a demandé de vérifier chaque constat avant de le corriger, de contester ceux qui me semblaient faux et de tout consigner ici.

Résultat : **aucun constat n'est faux.** J'en nuance trois sur des détails, sans en contester le fond. Tous décrivent des défauts que mes propres revues n'avaient pas vus. Le constat 5 contredit directement ce document, le constat 6 contredit le fichier de l'agent, et le constat 1 nuance ce que ce document laissait entendre.

## Les constats, vérifiés un par un

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

## Défaut trouvé en plus de l'audit
Le REX I6 contenait un bloc de 7 lignes qui parlait du mode classe (`ADRESSE=`, filtre de l'espace enseignant). Il venait de l'incrément 7, collé au mauvais endroit par le commit `9111c39` ; `inc-6` ne le contient pas. Je l'ai retiré : le texte reste à sa place dans la section I7.

## Questions au commanditaire : toujours ouvertes
Le message de l'audit prévoyait les réponses à mes deux questions de l'incrément 7, mais ses deux champs sont restés à l'état de gabarit (`[OUI / NON, préciser]`, `[pas encore fait / fait, résultat : ...]`). Je ne les interprète pas.
- **Espace enseignant réservé au PC en mode classe.** Rien ne change, et SPEC.md le garde « à confirmer ».
- **Essai réel avec un téléphone sur le Wi-Fi.** Considéré comme non fait. Les tests E2E de CLA-01 tournent sur une seule machine, avec des téléphones émulés : ils ne disent rien de l'isolation d'un vrai Wi-Fi d'école, qui reste le principal risque en classe.

Une question nouvelle, née de cet audit :
- **L'horloge du PC de classe.** Le déroulement d'une session se calcule à partir de l'horloge système du serveur. Si elle recule de 2 s, comme sur ce PC de développement :
  - le compte à rebours affiché remonte (essayé sous `make classe` : de 83 à 86 s) ;
  - la liste des connectés peut s'inverser (observé dans un test, sans l'horloge stable) ;
  - le créneau précédent peut revenir brièvement sur les téléphones, et une réponse donnée juste après un changement de créneau peut être refusée (déduit du code et des échecs de tests, pas essayé sous `make classe`).

  Je ne sais pas si un PC sous Windows, sans WSL2, a ce défaut : à contrôler sur le vrai PC de classe avant une évaluation notée. Le corriger pour de bon, si besoin, est une décision de conception : ne plus calculer le déroulement sur l'horloge système.

## Problèmes rencontrés
- **Le garde a analysé `2>&1` comme un séparateur de commandes.** Le `&` coupait la commande en deux : le test de pipe aurait regardé un « 1 » à la place de `make verify`. Ces redirections sont retirées avant l'analyse.
- **Mon propre test était trop strict.** Il interdisait « lecture seule » dans tout le fichier de l'agent, alors que celui-ci doit justement écrire qu'il ne l'est pas. Il porte maintenant sur la description, seule promesse faite à l'extérieur.
- **Mon premier comptage était faux, à 100 près.** J'ai d'abord annoncé 29 pipes, dont 5 après I5. Mon expression régulière s'arrêtait sur le `&` de `2>&1`, et donnait 0 pour la session même de l'incident, ce qui m'a alerté. Le chiffre juste vient du garde rejoué sur l'historique : 124, dont 43. Un outil de mesure se vérifie sur un cas dont on connaît la réponse.

## Ce que les revues ont trouvé
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

## Ce qui a bien marché
- **Vérifier sur pièces avant de corriger.** Les journaux ont apporté des précisions que le seul énoncé des constats ne donnait pas : l'origine exacte du `exit 0`, et l'écart entre la citation et la phrase du REX.
- **Essayer au lieu de raisonner sur le sandbox.** Le test qui l'empêche de valider `make verify` n'apparaissait dans aucune documentation.
- **Écrire les tests d'abord, pour de vrai.** 49 échecs observés et commités avant toute correction, sur la leçon même du constat 5.

## Ce que j'aurais dû savoir dès le départ
- **Une affirmation de preuve se relit comme une exigence.** « L'historique prouve » et « en lecture seule » étaient plus forts que les faits. Écrire ce qu'un mécanisme garantit, ce qu'il ne garantit pas, et ce qui ne tient qu'à la consigne.
- **Un incident rattrapé reste à consigner.** Les deux codes de retour et l'arrêt de I6 ont été vus sur le moment, puis jamais écrits : c'est ainsi qu'une vérification a pu repasser 43 fois dans un pipe après le premier incident.
- **Une consigne ne suffit pas à une règle qui compte.** Pour chaque règle, se demander ce qui la fait respecter, puis dire honnêtement si rien ne le fait.
- **Un inventaire se confronte à la liste des fonctions de l'outil,** pas à ce dont on se souvient.
- **Un test intermittent se mesure avant de s'expliquer.** J'ai réparé une cause plausible, sans sonde, et elle était fausse. Une explication qui tient sur un seul test ne vaut rien tant qu'elle n'a pas été confrontée aux échecs des autres.
- **L'horloge d'une machine n'est pas une donnée fiable.** Une application qui calcule des échéances doit le prévoir, et sa suite de tests aussi.
- **Un relecteur extérieur voit ce que mes revues ne peuvent pas voir.** Elles portent sur le diff. Aucune ne lit mes journaux, ni ne confronte ma méthode à ce que j'en dis.

## Choix techniques et leur raison
- **Aucune nouvelle dépendance.**
- **`.env.test` versionné plutôt qu'une clé éphémère en CI** : le même fichier sert partout, en local, en CI et dans les copies jetables, et un clone neuf peut tout vérifier sans générer de clé. Sa valeur ne protège rien, et son nom le dit.
- **Un incrément « R » sans exigence** : pas de test E2E marqué `spec`, car rien ne change pour l'utilisateur. Les comportements ajoutés sont des hooks, testés comme du code. Branche `inc/r-…`, tag `inc-r`, reconnus par le garde et le hook Stop.
