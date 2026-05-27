#!/usr/bin/env bash
# build.sh – Script exécuté par Render pendant le déploiement
# Dashboard Render > Build Command : ./build.sh
 
set -e   # Arrête le script si une commande échoue
 
echo "==> Installation des dépendances..."
pip install -r requirements.txt
 
echo "==> Application des migrations de base de données..."
flask db upgrade
 
echo "==> Création du compte secrétariat admin si inexistant..."
python seed.py
 
echo "==> Build terminé avec succès ✅"
 