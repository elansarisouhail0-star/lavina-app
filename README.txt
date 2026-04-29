# Méthode LAVINA - Application web multi-utilisateurs

Application Flask + SQLite pour réaliser des diagnostics maintenance selon 12 axes.

## Fonctions incluses

- Connexion multi-utilisateurs
- Compte administrateur initial
- Création d'utilisateurs
- Création de diagnostics par société/site/auditeur
- Sauvegarde des réponses
- Reprise d'un diagnostic plus tard
- Calcul automatique score / 3000 points
- Tableau de dépouillement
- Impression ou export PDF via le navigateur

## Installation

1. Installer Python 3.10 ou plus.
2. Ouvrir un terminal dans ce dossier.
3. Installer les dépendances :

```bash
pip install -r requirements.txt
```

4. Lancer l'application :

```bash
python app.py
```

5. Ouvrir dans le navigateur :

```text
http://localhost:5000
```

## Accès depuis plusieurs ordinateurs du même réseau

Sur l'ordinateur serveur, récupérer son adresse IP locale, par exemple `192.168.1.20`.

Depuis les autres ordinateurs du même réseau, ouvrir :

```text
http://192.168.1.20:5000
```

Il faut autoriser Python/Flask dans le pare-feu Windows si demandé.

## Compte initial

- Utilisateur : `admin`
- Mot de passe : `admin123`

Important : changez ce mot de passe rapidement.

## Production / Internet

Pour un usage professionnel accessible depuis Internet, il faut utiliser un vrai serveur avec :
- HTTPS
- mot de passe fort
- clé secrète Flask changée
- sauvegarde régulière de `lavina.db`
- idéalement Gunicorn + Nginx ou un hébergeur type Render/Railway/VPS.
