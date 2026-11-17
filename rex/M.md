# M — Méthode : audit borné, pytest sans collision, langue surveillée

## Objectif
Avant l'import AMC, le commanditaire a demandé trois ajustements de méthode, pour tenir les délais et la consommation :
1. au plus deux passages de `spec-auditor` par incrément ;
2. un mécanisme, et non plus une consigne, contre la collision entre le hook Stop et un pytest déjà lancé ;
3. consigner la dérive vers l'anglais d'I11 et trouver plus fiable qu'une consigne.

Aucune exigence de SPEC.md ne change, et `[tool.qcm] increment` reste à 11 : on vérifie avec `make accept INC=11`. Branche `inc/m-methode`, tag `inc-m`, comme R.

## Problèmes constatés
- **La dérive de langue d'I11 n'était pas consignée.** Sur 75 messages du fil principal d'I11, 71 étaient en anglais, sans compactage de contexte.
  - Le premier message en anglais arrive 20 s après le chargement du skill `increment`, alors que le commanditaire écrivait en français.
  - Quelques messages repassent en français au moment de poser la question sur ETU-10, puis tout est en anglais à partir de 9 h 49, une demi-heure avant `/simplify`.
  - La cause avancée jusque-là (les prompts anglais des skills de revue) ne suffit donc pas. Je ne connais pas la vraie cause. La règle de CLAUDE.md, présente depuis I0, n'a rien empêché.
- **Collision entre deux pytest.** Avant M, tous les pytest du dépôt partageaient `.test-db.sqlite3`. Je l'ai reproduite avant de corriger : un E2E d'I5, puis `make test` lancé 12 s plus tard, donnent 1 échec et 13 erreurs (32 « no such table: live_session », 14 « readonly database »). Deux `make test` simultanés passent par chance : leurs connexions déjà ouvertes gardent l'ancien fichier.

## Choix et leur raison
- **Une base de test par processus** (`.test-db-<pid>.sqlite3`). C'est le seul de ces mécanismes qui empêche vraiment la collision, quel que soit celui qui lance le second pytest : le hook, moi, un agent. Au démarrage, pytest supprime les bases dont le processus n'existe plus (pytest tué). J'ai préféré un fichier par pid à un fichier temporaire : les tests du mode classe lisent le nom dans les réglages pour le passer au serveur lancé à part, et ce nom ne change pas.
- **Le hook Stop ne lance pas `make check` pendant un pytest du projet** (worktrees compris, lu dans `/proc`). Même sans collision de base, un second pytest prend du processeur aux E2E à faible marge de temps, et vérifierait du code en cours de mutation. Il me renvoie attendre la fin du pytest, et le contrôle se fait à un arrêt suivant (correction après `/code-review` : la première version laissait l'arrêt passer en silence).
- **Langue : un réglage et un hook.**
  - `"language": "french"` dans `.claude/settings.json` place la consigne dans le prompt système, et non plus seulement dans CLAUDE.md. Cela reste une consigne.
  - `.claude/hooks/language.py` compte des mots-outils anglais et français, hors code. En hook PostToolUse, il m'avertit en cours de tour, dès le premier appel d'outil qui suit un message anglais : la dérive d'I11 a commencé au milieu d'un tour. Dans le hook Stop, il renvoie au travail un tour qui contient un message anglais, une fois par arrêt.
  - Je l'ai étalonné sur les journaux de toutes les sessions. Les quatre sessions tenues en français que j'ai rejouées, dont celle d'I10, ne déclenchent rien. Sur I11, il aurait averti 58 fois, une fois par message anglais suivi d'un appel, et renvoyé au travail 17 tours sur 23. Sur la session d'I0 à I4, 86 avertissements et 47 tours sur 78. Restent non détectés : des messages très courts (« Now README: »).
- **Audit borné.** Premier passage complet ; second passage facultatif, limité aux réserves bloquantes du premier, dont je transmets la liste ; ensuite, ce qui reste va dans le REX, sous « Réserves ouvertes ». Exception : une réserve qui touche la justesse des notes ou la séparation énoncé/propositions (AFF-01) reste bloquante. Je la corrige, puis je refais moi-même les contre-épreuves de l'auditeur, sans troisième passage. *C'est mon interprétation de la demande, à confirmer par le commanditaire.*

## Ce qui est garanti, et ce qui ne l'est pas
- **Imposé par un mécanisme :** deux pytest n'ont plus la même base de test. Un test d'intégration lance deux pytest à la fois sur un test qui écrit en base, et la démonstration réelle passe : le même E2E d'I5 et `make test` 12 s plus tard donnent 7 et 471 tests passés, sans aucune erreur de base.
- **Mécanisme, mais dépendant de Linux :** le hook Stop qui ne lance pas `make check`. Lancé à la main pendant un pytest, il a répondu en 0,7 s sans le lancer. Sans `/proc`, il ne voit rien et lance `make check` comme avant ; la base par processus protège alors toujours.
- **Détection heuristique, après coup :** le hook de langue. Le message anglais est déjà affiché quand il réagit, et un message court ou mêlé de français peut passer. Il ne laisse passer sans contrôle que l'arrêt qui suit son propre renvoi ; après un renvoi de `stop_check.py` (procédure, pytest en cours), la langue est contrôlée quand même.
- **Consigne seulement :** le réglage `language`, la règle 7 de CLAUDE.md, et le plafond de deux passages d'audit. Le hook Stop ne voit que la ligne `Audit spec-auditor : <commit>`, pas le nombre de passages.

## Problèmes rencontrés
- **Mes tests unitaires du hook Stop passaient, et le hook ne marchait pas.** Je l'ai essayé dans une vraie session jetable (`claude -p`, dans le scratchpad) : il laissait s'arrêter un tour en anglais. Au moment du hook Stop, le journal n'a pas encore le dernier message, qui n'arrive que dans le champ `last_assistant_message` de l'entrée du hook. Mes faux journaux, eux, le contenaient. Le hook lit désormais les deux, sans compter deux fois le même message, et l'essai réel renvoie bien au travail, une seule fois.
- **Un avertissement par appel, et non par message.** Plusieurs appels d'outil parallèles qui suivent le même message donnaient chacun un avertissement : 107 sur I11 pour 58 messages. Seul le premier appel en reçoit un maintenant.
- **Le hook PostToolUse n'a pas agi dans la session où je l'ai ajouté.** J'ai écrit exprès un message en anglais avant un appel : aucun avertissement. Rejoué à la main sur le journal de cette session, le hook le détecte, et dans une session neuve il avertit bien. Hypothèse, non vérifiée : Claude Code lit les hooks au démarrage de la session.
- **Le garde-fou `guard_bash.py` a refusé quatre de mes commandes**, chaque fois une vérification suivie de `;` ou d'un pipe. Il a fonctionné comme prévu ; je suis passé par des scripts qui rendent le code de retour, ou par une redirection vers un fichier.
- **Le formateur a déplié mes listes de mots en un mot par ligne.** Je les écris maintenant comme une chaîne découpée par `split()`.

## Revues
- **`/simplify`** :
  - *Retenu* : la langue devient une entrée Stop à part, pour qu'une erreur de ce hook ne bloque pas `make check`, et chaque ligne du journal n'est analysée qu'une fois.
  - *Retenu* : `pytest_running` ne résout le dossier courant que des processus pytest.
  - *Écarté* : lire une fin de journal plus courte dans le hook PostToolUse. Le coût mesuré est d'environ 45 ms par appel d'outil.
- **`/code-review`** : dix constats.
  - *Corrigés (six)* :
    - le hook Stop laissait l'arrêt passer en silence pendant un pytest ;
    - l'avertissement de langue se rabattait sur un appel sans rapport (appel d'un sous-agent) ;
    - un rappel système ou un message d'une autre session ouvrait un nouveau tour et masquait les messages précédents ;
    - le point final faisait ignorer le mot qui le précède (« Done. All green. » passait) ;
    - le test de concurrence ne garantissait pas que les deux pytest se chevauchent (rendez-vous ajouté, contre-épreuve sur une base partagée : il échoue) ;
    - CLAUDE.md attribuait la langue à `stop_check.py`.
  - *Corrigé, septième constat* : l'entrée de langue ne contrôlait jamais l'arrêt qui suit un renvoi de `stop_check.py`, soit un arrêt sur deux d'un incrément inachevé. Elle ne saute plus que l'arrêt qui suit son propre renvoi, reconnu à son texte dans le journal.
  - *Écartés* :
    - le coût du hook PostToolUse (voir `/simplify`) ;
    - une base gardée si son pid est réutilisé (le sens prudent), ou supprimée par un pytest d'un autre espace de noms de processus (aucun conteneur ne partage ce dépôt) ;
    - `--reuse-db`, que ni le Makefile ni la CI n'utilisent.
- **`/security-review`** : aucune vulnérabilité au-dessus du seuil de confiance.

## Audit
- **Un seul passage de `spec-auditor`**, sur 38fccc1 : 40 mutations, 32 détectées, aucune réserve bloquante.
  - Les huit survivantes étaient des faiblesses :
    - le branchement de `remove_stale` au démarrage de pytest ;
    - la branche `PermissionError` ;
    - les seuils de l'heuristique de langue et l'apostrophe typographique ;
    - l'arrêt de la remontée à un message entrant ;
    - une charge JSON qui n'est pas un objet ;
    - le matcher `"*"`.
  - Une seule n'a pas d'effet observable : la ligne coupée en tête de la fin du journal.
  - J'ai ajouté un test pour chaque faiblesse et rejoué les mutations : toutes sont détectées. Le premier test de l'apostrophe (« I’m ») laissait encore passer sa mutation, parce que « i » est déjà un mot-outil anglais : il porte maintenant sur « j’ai ».
  - Pas de second passage : il ne porterait que sur des réserves bloquantes, et il n'y en avait aucune.
- **Ce que l'auditeur n'a pas pu vérifier.** Les chiffres d'étalonnage de la détection (aucun faux positif, tous les messages anglais d'I11 détectés) sont empiriques, mesurés sur les journaux locaux de Claude Code, et aucun test ne les reproduit. Un exemple de message non détecté cité plus haut ne figure plus dans les journaux présents.
- **Précision de CLAUDE.md, après l'audit.** Le garde `/proc` ne voit que les worktrees placés sous le dossier du projet (`.claude/worktrees/`), pas un `git worktree add ../x`.

Audit spec-auditor : 38fccc1

## Ce que j'aurais dû savoir dès le départ
- **Un hook se teste dans une vraie session.** Un faux journal ne reproduit que ce que je crois savoir du format, et c'est là que se trouvait le défaut.
- **Une règle qui dépend de ma vigilance ne tient pas dans une longue session.** Deux collisions en I11 malgré la règle de CLAUDE.md, et 71 messages anglais malgré la règle 7. Il faut chercher d'abord le mécanisme.
