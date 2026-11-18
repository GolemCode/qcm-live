# QCM Live : guide de l'enseignant

QCM Live projette les questions d'un QCM au tableau ; les étudiants répondent sur leur téléphone. Tout tourne sur votre PC : aucun serveur extérieur, aucune donnée ne quitte la salle.

## 1. Installer (une fois)

**Linux.** Dans un terminal :

```sh
curl -LsSf https://raw.githubusercontent.com/GolemCode/qcm-live/main/install.sh | sh
```

**Windows.** Dans PowerShell :

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/GolemCode/qcm-live/main/install.ps1 | iex"
```

L'installation ne demande pas de droits d'administrateur. Elle installe au besoin [uv](https://docs.astral.sh/uv/), qui installe Python, puis vous demande :

- **votre compte enseignant** : un identifiant et un mot de passe, demandé deux fois (il ne s'affiche pas pendant la saisie) ;
- **s'il faut ajouter la démonstration** : un QCM et un groupe de six étudiants fictifs, pour vous faire la main. Elle reste légère : la démonstration complète, avec une session passée et ses résultats, se lance à part (section 2) et n'entre jamais dans vos données.

Elle crée l'icône « QCM Live » dans le menu des applications, et la commande `qcm-live`.

## 2. Découvrir en 10 minutes : la démonstration complète

Pour tout essayer sans toucher à vos données, dans un terminal :

```sh
qcm-live demo
```

QCM Live s'ouvre sur une **base à part**, `demo.sqlite3` dans son dossier de données, recréée à chaque lancement : vos QCM, groupes et résultats ne sont pas ouverts, et rien n'est sauvegardé. Le terminal affiche l'identifiant `demo` et son mot de passe, nouveau à chaque lancement. Tout est fictif : trois QCM importés de fichiers AMC (deux de mathématiques, un d'informatique), deux groupes « L1 Sciences » (celui de cette année, 70 étudiants, et celui de l'an dernier), une session passée la semaine dernière, et un QCM composé. Ce que vous y changez disparaît au lancement suivant ; fermer le terminal l'arrête.

1. **Se connecter** (1 min). Identifiant `demo` et le mot de passe affiché dans le terminal.
2. **Les QCM** (2 min). « QCM » : les trois fichiers importés, dont « Mathématiques : Fonctions et dérivées », et « Mathématiques : révisions », composé à partir des deux fichiers de mathématiques. Ouvrez-en un : formules, code et images s'affichent comme au tableau.
3. **Déjà posées** (1 min). Ouvrez « Mathématiques : révisions », puis « Modifier le QCM ». Dans « Marquer les questions déjà posées au groupe », choisissez « L1 Sciences » de cette année, puis « Marquer » : la colonne « Déjà posée » signale les questions de la session passée, et à combien d'étudiants.
4. **Les versions** (1 min). « Banque de questions » : la question sur la dérivée de x³ a été reformulée après la session ; « Versions précédentes » montre l'ancienne, que les résultats passés gardent.
5. **Les groupes** (1 min). « Groupes » : deux « L1 Sciences », d'années différentes. Le n° de liste désigne l'étudiant ; le numéro étudiant n'est jamais projeté.
6. **Les résultats** (2 min). « Sessions », puis « Résultats » de la session terminée. La page s'ouvre notes masquées, car elle peut être projetée : « Afficher les notes » montre la note de chaque étudiant et sa note sur 20 ; les absents sont signalés. « Télécharger le CSV » donne le détail des réponses.
7. **Lancer une session** (1 min). « Sessions », puis « Lancer une session » : « Mathématiques : révisions », le groupe « L1 Sciences » de cette année, puis « Lancer ». QCM Live prévient que des questions ont déjà été posées à ce groupe : « Revenir » pour changer de QCM, ou « Lancer quand même ».
8. **Au tableau** (1 min). La page à projeter montre l'adresse et le QR code. « Tester avec mon téléphone » vérifie que votre téléphone joint le PC ; scannez ensuite le QR code, choisissez un nom de la liste, puis « Démarrer » au tableau.

## 3. Préparer un cours

Lancez QCM Live (icône ou commande `qcm-live`) : le navigateur s'ouvre sur l'espace enseignant.

1. **Le QCM.** « QCM », puis « Importer un fichier AMC » : choisissez le fichier `.txt` d'AMC, puis « Analyser ». Un récapitulatif liste les questions importées et celles qui sont écartées (avec la ligne et la raison). « Importer » crée le QCM, avec le barème du fichier.
   - Essayez d'abord un ancien QCM, et comparez quelques notes avec celles d'AMC.
   - Réimporter le même fichier complète son QCM : les questions retirées ou supprimées reviennent à leur place, vos modifications restent.
   - **Avec des images**, importez une **archive ZIP** qui contient le fichier `.txt` et ses images, aux chemins cités dans le fichier (`!images/graphe.png!` : un dossier `images/` à côté du `.txt`). Les formats acceptés sont PNG, JPEG et SVG, 2 Mo au plus par image. Une question qui cite une image PDF ou EPS est écartée : convertissez l'image en PNG. Une image absente de l'archive fait refuser le fichier, avec la ligne de la question.
   - Formules (`[[…]]`, `[latex]…[/latex]`), code (`[verbatim]`, `[|…|]`) et mise en forme (`[*gras*]`, `[_italique_]`, `[/souligné/]`) passent comme dans AMC. Tout fonctionne sans Internet : rien n'est chargé d'un autre serveur que votre PC.
   - **Écrire une question à la main** : dans le formulaire, énoncé et propositions s'écrivent en LaTeX simplifié. `$\frac{1}{2}$` pour une formule, `\texttt{x = 1}` pour du code en ligne, `\begin{verbatim}` … `\end{verbatim}` pour un bloc de code, `\textbf{…}`, `\textit{…}`, `\underline{…}` pour la mise en forme. Le reste s'écrit tel quel (« 50 % », « A & B ») ; seuls `$` et `\` sont spéciaux : `\$` pour un dollar. Une image ne s'ajoute que par l'import ; le formulaire garde celles de la question.
   - Une formule que QCM Live ne sait pas afficher reste écrite avec son code, en rouge : voir « Formules qui s'affichent en rouge », ci-dessous.
   - La démonstration est une archive : pour la réimporter à la main, mettez en ZIP le dossier `demo/` (le `.txt` et `images/`).
   - Pour composer un QCM, cochez ses questions (« Modifier le QCM ») ; « Reprendre dans un nouveau QCM » en fait une copie à retoucher. Modifier une question qui a déjà servi en crée une nouvelle version : les résultats passés ne changent pas.
2. **Le groupe.** « Groupes », puis « Importer un groupe » : un fichier CSV (70 étudiants au plus) qui commence par la ligne `n°;numéro étudiant;nom`, puis une ligne par étudiant, par exemple `12;21904567;DUPONT Jeanne`.
   - Le **n°** est celui de votre liste d'appel : un entier de 1 à 999, chacun une fois ; des trous sont permis. C'est lui qui désigne l'étudiant sur son téléphone et dans les résultats.
   - Le **numéro étudiant** peut rester vide (`13;;MARTIN Paul`). Il n'est jamais affiché sur les téléphones ni projeté.
   - Un ancien fichier `numéro;nom` reste accepté : chaque étudiant reçoit alors pour n° son rang dans le fichier.

### Formules qui s'affichent en rouge

QCM Live affiche les formules avec KaTeX, sur votre PC. KaTeX connaît l'essentiel des commandes mathématiques de LaTeX, pas toutes ([liste des commandes prises en charge](https://katex.org/docs/supported.html)). Une formule qu'il ne sait pas afficher reste écrite avec son code, **en rouge** ; le survol de la souris en donne la raison. La question n'est pas écartée : elle s'importe, mais ses étudiants verraient ce code.

**Pourquoi.**

- **Une commande inconnue de KaTeX**, que LaTeX accepte pourtant.
- **Une macro personnelle** : une commande définie par `\newcommand` dans l'en-tête de votre document LaTeX, par exemple `\vect{u}`. Le fichier AMC-TXT ne contient pas cette définition, et QCM Live ne la connaît pas.
- **Une commande d'un paquet** que votre document charge par `\usepackage`, par exemple `\SI{3}{\metre\per\second}` du paquet `siunitx`.
- Une formule mal écrite : une accolade ou un `$` oublié.

**Comment le voir.** Dès l'import : le **récapitulatif** montre chaque question telle qu'elle s'affichera, formules comprises ; une formule en rouge s'y voit avant de cliquer sur « Importer ». Ensuite, dans la « Banque de questions ».

**Quoi faire.**

- Remplacez la macro par sa définition (`\vect{u}` devient `\overrightarrow{u}`), et la commande du paquet par une écriture que KaTeX connaît (`3\,\mathrm{m/s}`), dans le fichier `.txt`, puis importez-le de nouveau.
- Ou corrigez la question dans la « Banque de questions » : « Modifier ». Si elle a déjà servi, une nouvelle version est créée et les résultats passés ne changent pas.

## 4. En classe

1. **Lancez QCM Live** sur le PC relié au vidéoprojecteur. Le terminal qui s'ouvre affiche l'adresse que les téléphones ouvriront ; **laissez-le ouvert** : le fermer (ou Ctrl+C) arrête QCM Live.
2. **Lancez la session.** « Sessions », puis « Lancer une session » : QCM, groupe, nombre de questions affichées à la fois, durée par question. Le tableau projette l'adresse et un QR code.
3. **Vérifiez avec votre téléphone** (avant le premier cours dans une salle) : au tableau, « Tester avec mon téléphone ». Scannez le QR code : « Connexion réussie » sur le téléphone, « Téléphone connecté » sur le PC.
   - **Rien ne vient ?** Votre PC a peut-être plusieurs adresses (Wi-Fi, câble, partage de connexion, VPN). Au tableau, « Changer d'adresse » : choisissez celle du réseau où sont les téléphones, puis refaites l'essai. Pas besoin de relancer.
   - **Pare-feu.** S'il en détecte un, QCM Live l'affiche, avec la commande qui laisse passer les téléphones. Il ne la lance jamais : c'est à vous de juger.
   - **Wi-Fi de l'école.** Certains réseaux isolent les appareils entre eux : les téléphones ne joignent alors jamais le PC. Solution : le partage de connexion de votre PC, ou un petit routeur Wi-Fi à vous.
4. **Faites passer.** Les étudiants ouvrent l'adresse (ou scannent le QR code), choisissent leur nom dans la liste et confirment. Un nom déjà choisi apparaît grisé, « déjà connecté » : si ce n'est pas le bon étudiant, « Gérer les connectés » (en haut du tableau, page à ne pas projeter) permet de le libérer avant le départ. « Démarrer » quand tout le monde est là ; « +10 s » ajoute du temps à la question en cours.

## 5. Après

Une fois la session terminée : « Résultats ». La page s'ouvre **notes masquées** (elle peut être projetée par erreur) ; « Afficher les notes » les montre. « Télécharger le CSV » donne, pour chaque étudiant, ses réponses, ses points, sa note et sa **note sur 20**.

## 6. Sauvegardes

QCM Live sauvegarde vos données **à chaque lancement**, dans le dossier `QCM Live/sauvegardes` de votre dossier personnel. Les 10 dernières sont gardées. Copiez-en une de temps en temps sur une clé USB.

Dans un terminal, QCM Live arrêté :

| Commande | Effet |
|---|---|
| `qcm-live sauvegarder` | une sauvegarde, tout de suite |
| `qcm-live restaurer` | liste les sauvegardes, puis remplace vos données par celle choisie, après confirmation. Les données actuelles sont d'abord sauvegardées. |
| `qcm-live restaurer <fichier.zip>` | restaure ce fichier (une copie sur clé USB, par exemple) |

## 7. Mettre à jour, désinstaller

- **Mettre à jour** : relancez la ligne d'installation. Le code est remplacé ; vos QCM, groupes, résultats et votre compte restent.
- **Autre compte enseignant** : `qcm-live compte`.
- **Autre port** (si 8000 est pris) : `qcm-live --port 8080`.
- **Désinstaller** (Linux) : supprimez `~/.local/share/qcm-live`, `~/.local/bin/qcm-live` et `~/.local/share/applications/qcm-live.desktop`. Sous Windows : le dossier `%LOCALAPPDATA%\qcm-live`, le fichier `%USERPROFILE%\.local\bin\qcm-live.cmd` et le raccourci « QCM Live » du menu Démarrer. Le dossier `QCM Live/sauvegardes` n'est jamais supprimé par QCM Live.

## 8. Revenir à une version précise (dépannage)

Si la dernière version pose problème le jour d'un cours, vous pouvez réinstaller une version antérieure : chaque version livrée porte une étiquette (`inc-19`, `inc-d`, `inc-17`…), visible dans la page [Tags](https://github.com/GolemCode/qcm-live/tags) du dépôt. Vos QCM, groupes, résultats et votre compte restent, comme pour une mise à jour. Remplacez `inc-d` par l'étiquette voulue dans les deux lignes.

**Linux.** Dans un terminal :

```sh
curl -LsSf https://github.com/GolemCode/qcm-live/archive/refs/tags/inc-d.tar.gz -o "$HOME/qcm-live-inc-d.tar.gz"
curl -LsSf https://raw.githubusercontent.com/GolemCode/qcm-live/inc-d/install.sh | QCM_LIVE_ARCHIVE="$HOME/qcm-live-inc-d.tar.gz" sh
```

**Windows.** Dans PowerShell :

```powershell
Invoke-WebRequest -UseBasicParsing https://github.com/GolemCode/qcm-live/archive/refs/tags/inc-d.zip -OutFile "$env:TEMP\qcm-live-inc-d.zip"
$env:QCM_LIVE_ARCHIVE = "$env:TEMP\qcm-live-inc-d.zip"; powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/GolemCode/qcm-live/inc-d/install.ps1 | iex"; Remove-Item Env:QCM_LIVE_ARCHIVE
```

La première ligne télécharge le code de cette version ; la seconde lance l'installation de la même version, à partir du fichier téléchargé. Comme pour une mise à jour, rien ne vous est demandé : votre compte reste. Le fichier téléchargé peut ensuite être supprimé.

- **Jusqu'où revenir** : depuis `inc-19`, `inc-d` et `inc-17` lisent vos données telles quelles. Une version plus ancienne (`inc-16` et avant) ne connaît pas les images ni les versions récentes des questions : restaurez alors, après l'installation, une sauvegarde faite avec cette version-là (section 6).
- **Revenir à la dernière version** : relancez la ligne d'installation habituelle (section 1).
