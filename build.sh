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
if [ ! -d "migrations" ]; then
    echo "  Initialisation des migrations (premier déploiement)..."
    flask db init
    flask db migrate -m "Initial migration"

    echo "  Nettoyage de l'historique alembic en base (évite les conflits)..."
    python -c "
import os
os.environ.setdefault('FLASK_ENV', 'production')
from app import create_app
from app.models import db
from sqlalchemy import text
app = create_app('production')
with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(text('DROP TABLE IF EXISTS alembic_version'))
        conn.commit()
    print('  Table alembic_version réinitialisée.')
"
else
    echo "  Dossier migrations existant — application des migrations uniquement."
fi

flask db upgrade

echo "==> Création du compte secrétariat admin si inexistant..."
python seed.py

echo "==> Build terminé avec succès ✅"