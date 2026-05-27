#!/usr/bin/env bash
set -e

echo "==> Installation des dépendances..."
pip install -r requirements.txt

echo "==> Vérification DATABASE_URL..."
python -c "
import os, sys
db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    print('ERREUR : DATABASE_URL non définie !', file=sys.stderr)
    sys.exit(1)
print(f'  OK : {db_url[:45]}...')
"

echo "==> Application des migrations..."
if [ ! -d "migrations" ]; then
    echo "  Dossier migrations introuvable. Initialisation..."
    flask db init
    flask db migrate -m "Initial migration"
    flask db upgrade
else
    echo "  Dossier migrations existant. Tentative d'upgrade..."
    if ! flask db upgrade; then
        echo "  Échec de l'upgrade (probablement révision manquante)."
        echo "  Recalage de la base sur la dernière révision..."
        flask db stamp head
        echo "  Nouvelle tentative d'upgrade..."
        flask db upgrade
    fi
fi

echo "==> Création du compte admin..."
python seed.py

echo "==> Build terminé ✅"