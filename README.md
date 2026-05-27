# ENSEA — Application de suivi des notes

Application web Flask permettant aux **étudiants** de consulter leurs notes en permanence et au **secrétariat** de gérer les résultats (étudiants, enseignants, classes, matières, enseignements, types de notes, imports/exports Excel, statistiques, etc.).

---

## Stack technique

- **Backend** : Flask 3 (Python 3.10+)
- **Base de données** : PostgreSQL
- **ORM** : Flask-SQLAlchemy + Flask-Migrate
- **Auth** : Flask-Login (deux rôles : `secretariat`, `etudiant`)
- **Formulaires** : Flask-WTF
- **Mail** : Flask-Mail
- **Hachage** : bcrypt
- **Excel** : pandas + openpyxl
- **PDF** : reportlab
- **Frontend** : Bootstrap 5, DataTables, Chart.js, Bootstrap Icons

---

## Installation locale

### 1. Cloner / extraire le projet

```bash
cd Base_Données
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer PostgreSQL

Créer une base `ensea_notes` :

```sql
CREATE DATABASE ensea_notes;
```

### 5. Variables d'environnement

```bash
cp .env.example .env
# Éditer .env : SECRET_KEY, DATABASE_URL, MAIL_*
```

> **Note mail** : en développement, laisser `MAIL_USERNAME` et `MAIL_PASSWORD` vides. Les mots de passe générés s'afficheront alors dans la console au lieu d'être envoyés par email.

### 6. Initialiser la base

```bash
python seed.py            # tables + compte admin
python seed.py --demo     # ajoute des données de démonstration
python seed.py --reset    # DROP + recrée tout
```

### 7. Lancer l'application

```bash
python run.py
```

Application disponible sur **http://localhost:5000**

---

## Comptes par défaut

### Secrétariat (admin)
- **Email** : `admin@ensea.ci`
- **Mot de passe** : `Admin@ENSEA2025`
- **URL** : `/auth/secretariat`

### Étudiants
Créés via l'interface ou `seed.py --demo`. Le mot de passe est généré aléatoirement et envoyé par email (ou affiché en console en dev).

URL de connexion étudiant : `/auth/etudiant`

---

## Règles métier importantes

- **Notes permanentes** : jamais supprimées, seulement remplacées par UPDATE (event listener SQLAlchemy).
- **Mot de passe étudiant** : 8+ caractères, 1 majuscule, 1 minuscule, 1 chiffre, 1 caractère spécial (`- . _ @ + *`). Unicité globale en clair (vérifiée avant hachage).
- **Année scolaire** : format `YYYY-YYYY`, année2 = année1+1, pas postérieure à l'année courante + 1.
- **Notes** : valeur entre 0 et 20 (CheckConstraint BDD).
- **Email** : unique par table (étudiant, secrétariat, enseignant).

---

## Structure du projet

```
Base_Données/
├── run.py                 # Point d'entrée
├── config.py              # Configuration
├── seed.py                # Initialisation BDD
├── requirements.txt
├── Procfile               # Render
├── vercel.json            # Vercel
├── .env.example
├── README.md
└── app/
    ├── __init__.py        # Factory create_app()
    ├── models.py          # 12 tables SQLAlchemy
    ├── forms.py           # Tous les formulaires WTForms
    ├── blueprints/
    │   ├── auth/          # Connexion / reset
    │   ├── secretariat/   # Interface secrétariat
    │   └── etudiant/      # Interface étudiant
    ├── templates/         # Jinja2 (base.html + sous-dossiers)
    ├── static/
    │   ├── css/custom.css
    │   └── js/main.js
    └── utils/
        ├── password.py    # Génération/hash/unicité
        ├── stats.py       # Statistiques descriptives
        ├── email_utils.py
        ├── excel.py
        └── pdf.py
```

---

## Déploiement

### Render

1. Pousser le code sur GitHub.
2. Créer un service **Web Service** sur Render.
3. Variables d'env : `SECRET_KEY`, `DATABASE_URL`, `MAIL_*`.
4. Build command : `pip install -r requirements.txt`
5. Start command : `gunicorn run:app` (déjà dans le `Procfile`).
6. Lancer `python seed.py` une seule fois via le shell Render.

### Vercel

Voir `vercel.json`. Note : Vercel est moins adapté pour des apps Flask avec PostgreSQL persistant.

---

## Migrations Flask-Migrate

```bash
flask db init                       # une seule fois
flask db migrate -m "description"
flask db upgrade
```

> Définir `FLASK_APP=run.py` avant chaque commande `flask` si nécessaire.

---

## Aide / Support

- Toute suppression d'une **note** est interdite (règle métier renforcée par event listener).
- Les imports Excel produisent un **rapport détaillé** (créés, mis à jour, ignorés, erreurs).
- Les statistiques sont recalculées **à la volée** à chaque visualisation.

# A ignorer
Dans le terminal, à la racine du projet (là où se trouve run.py), exécutez :
flask db migrate -m "Ajout de la colonne email au modèle Utilisateur"
Appliquez la migration sur votre base locale pour valider :
flask db upgrade

5. Commiter et pousser les fichiers de migration

6. Déploiement automatique sur Render
Une fois le push effectué sur GitHub, Render détecte le changement et lance un nouveau build.
Le script build.sh (la version recommandée que je vous ai donnée) exécute flask db upgrade, ce qui applique la nouvelle migration à la base de production.

La table alembic_version sur Render passe à la nouvelle révision, et la structure est mise à jour sans perte de données.