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
- **s'il faut ajouter la démonstration** : un QCM et un groupe de six étudiants fictifs, pour vous faire la main.

Elle crée l'icône « QCM Live » dans le menu des applications, et la commande `qcm-live`.

## 2. Préparer un cours

Lancez QCM Live (icône ou commande `qcm-live`) : le navigateur s'ouvre sur l'espace enseignant.

1. **Le QCM.** « QCM », puis « Importer un fichier AMC » : choisissez le fichier `.txt` d'AMC, puis « Analyser ». Un récapitulatif liste les questions importées et celles qui sont écartées (avec la ligne et la raison). « Importer » crée le QCM, avec le barème du fichier.
   - Essayez d'abord un ancien QCM, et comparez quelques notes avec celles d'AMC.
   - Réimporter le même fichier complète son QCM : les questions retirées ou supprimées reviennent à leur place, vos modifications restent.
   - **Avec des images**, importez une **archive ZIP** qui contient le fichier `.txt` et ses images, aux chemins cités dans le fichier (`!images/graphe.png!` : un dossier `images/` à côté du `.txt`). Les formats acceptés sont PNG, JPEG et SVG, 2 Mo au plus par image. Une question qui cite une image PDF ou EPS est écartée : convertissez l'image en PNG. Une image absente de l'archive fait refuser le fichier, avec la ligne de la question.
   - Formules (`[[…]]`, `[latex]…[/latex]`), code (`[verbatim]`, `[|…|]`) et mise en forme (`[*gras*]`, `[_italique_]`, `[/souligné/]`) passent comme dans AMC. Tout fonctionne sans Internet : rien n'est chargé d'un autre serveur que votre PC.
   - **Écrire une question à la main** : dans le formulaire, énoncé et propositions s'écrivent en LaTeX simplifié. `$\frac{1}{2}$` pour une formule, `\texttt{x = 1}` pour du code en ligne, `\begin{verbatim}` … `\end{verbatim}` pour un bloc de code, `\textbf{…}`, `\textit{…}`, `\underline{…}` pour la mise en forme. Le reste s'écrit tel quel (« 50 % », « A & B ») ; seuls `$` et `\` sont spéciaux : `\$` pour un dollar. Une image ne s'ajoute que par l'import ; le formulaire garde celles de la question.
   - Une formule mal écrite s'affiche avec son code, soulignée en rouge : relisez-la dans la banque avant le cours.
   - La démonstration est une archive : pour la réimporter à la main, mettez en ZIP le dossier `demo/` (le `.txt` et `images/`).
   - Pour composer un QCM, cochez ses questions (« Modifier le QCM ») ; « Reprendre dans un nouveau QCM » en fait une copie à retoucher. Modifier une question qui a déjà servi en crée une nouvelle version : les résultats passés ne changent pas.
2. **Le groupe.** « Groupes », puis « Importer un groupe » : un fichier CSV (70 étudiants au plus) qui commence par la ligne `n°;numéro étudiant;nom`, puis une ligne par étudiant, par exemple `12;21904567;DUPONT Jeanne`.
   - Le **n°** est celui de votre liste d'appel : un entier de 1 à 999, chacun une fois ; des trous sont permis. C'est lui qui désigne l'étudiant sur son téléphone et dans les résultats.
   - Le **numéro étudiant** peut rester vide (`13;;MARTIN Paul`). Il n'est jamais affiché sur les téléphones ni projeté.
   - Un ancien fichier `numéro;nom` reste accepté : chaque étudiant reçoit alors pour n° son rang dans le fichier.

## 3. En classe

1. **Lancez QCM Live** sur le PC relié au vidéoprojecteur. Le terminal qui s'ouvre affiche l'adresse que les téléphones ouvriront ; **laissez-le ouvert** : le fermer (ou Ctrl+C) arrête QCM Live.
2. **Lancez la session.** « Sessions », puis « Lancer une session » : QCM, groupe, nombre de questions affichées à la fois, durée par question. Le tableau projette l'adresse et un QR code.
3. **Vérifiez avec votre téléphone** (avant le premier cours dans une salle) : au tableau, « Tester avec mon téléphone ». Scannez le QR code : « Connexion réussie » sur le téléphone, « Téléphone connecté » sur le PC.
   - **Rien ne vient ?** Votre PC a peut-être plusieurs adresses (Wi-Fi, câble, partage de connexion, VPN). Au tableau, « Changer d'adresse » : choisissez celle du réseau où sont les téléphones, puis refaites l'essai. Pas besoin de relancer.
   - **Pare-feu.** S'il en détecte un, QCM Live l'affiche, avec la commande qui laisse passer les téléphones. Il ne la lance jamais : c'est à vous de juger.
   - **Wi-Fi de l'école.** Certains réseaux isolent les appareils entre eux : les téléphones ne joignent alors jamais le PC. Solution : le partage de connexion de votre PC, ou un petit routeur Wi-Fi à vous.
4. **Faites passer.** Les étudiants ouvrent l'adresse (ou scannent le QR code), choisissent leur nom dans la liste et confirment. Un nom déjà choisi apparaît grisé, « déjà connecté » : si ce n'est pas le bon étudiant, « Gérer les connectés » (en haut du tableau, page à ne pas projeter) permet de le libérer avant le départ. « Démarrer » quand tout le monde est là ; « +10 s » ajoute du temps à la question en cours.

## 4. Après

Une fois la session terminée : « Résultats ». La page s'ouvre **notes masquées** (elle peut être projetée par erreur) ; « Afficher les notes » les montre. « Télécharger le CSV » donne, pour chaque étudiant, ses réponses, ses points, sa note et sa **note sur 20**.

## 5. Sauvegardes

QCM Live sauvegarde vos données **à chaque lancement**, dans le dossier `QCM Live/sauvegardes` de votre dossier personnel. Les 10 dernières sont gardées. Copiez-en une de temps en temps sur une clé USB.

Dans un terminal, QCM Live arrêté :

| Commande | Effet |
|---|---|
| `qcm-live sauvegarder` | une sauvegarde, tout de suite |
| `qcm-live restaurer` | liste les sauvegardes, puis remplace vos données par celle choisie, après confirmation. Les données actuelles sont d'abord sauvegardées. |
| `qcm-live restaurer <fichier.zip>` | restaure ce fichier (une copie sur clé USB, par exemple) |

## 6. Mettre à jour, désinstaller

- **Mettre à jour** : relancez la ligne d'installation. Le code est remplacé ; vos QCM, groupes, résultats et votre compte restent.
- **Autre compte enseignant** : `qcm-live compte`.
- **Autre port** (si 8000 est pris) : `qcm-live --port 8080`.
- **Désinstaller** (Linux) : supprimez `~/.local/share/qcm-live`, `~/.local/bin/qcm-live` et `~/.local/share/applications/qcm-live.desktop`. Sous Windows : le dossier `%LOCALAPPDATA%\qcm-live`, le fichier `%USERPROFILE%\.local\bin\qcm-live.cmd` et le raccourci « QCM Live » du menu Démarrer. Le dossier `QCM Live/sauvegardes` n'est jamais supprimé par QCM Live.
