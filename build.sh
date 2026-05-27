#!/usr/bin/env bash
# build.sh – Render deployment script
set -e

echo "==> Installation des dépendances..."
pip install -r requirements.txt

echo "==> Vérification de la connexion base de données..."
python -c "
import os, sys
db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    print('ERREUR : DATABASE_URL non définie !', file=sys.stderr)
    sys.exit(1)
print(f'  DATABASE_URL trouvée : {db_url[:40]}...')
"

echo "==> Initialisation/Migration de la base de données..."
# Si le dossier migrations n'existe pas encore, on l'initialise
if [ ! -d "migrations" ]; then
    echo "  Premier déploiement : initialisation des migrations..."
    flask db init
    flask db migrate -m "Initial migration"
else
    echo "  Dossier migrations existant, application des migrations..."
fi
flask db upgrade

echo "==> Création du compte secrétariat admin si inexistant..."
python seed.py

echo "==> Build terminé avec succès ✅"