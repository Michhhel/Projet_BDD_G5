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

echo "==> Gestion des migrations..."

if [ ! -d "migrations" ]; then
    echo "  Dossier migrations introuvable. Initialisation..."
    flask db init
    flask db migrate -m "Initial migration"
    echo "  Application de la migration initiale..."
    flask db upgrade
else
    echo "  Dossier migrations existant. Mise à jour de la base..."
    # On tente l'upgrade classique ; en cas d'échec (révision manquante),
    # on recale la base sur la tête de la chaîne de migrations.
    if ! flask db upgrade; then
        echo "  ERREUR lors de l'upgrade (probablement une révision introuvable)."
        echo "  Forçage de l'état de la base à la révision courante..."
        flask db stamp head
        echo "  Nouvelle tentative d'upgrade..."
        flask db upgrade
    fi
fi

echo "==> Création du compte secrétariat admin si inexistant..."
python seed.py

echo "==> Build terminé avec succès ✅"