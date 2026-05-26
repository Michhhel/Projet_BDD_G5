# =============================================================================
# seed.py – Initialisation de la base ENSEA
# =============================================================================
# Usage :
#   python seed.py             → crée les tables + compte admin par défaut
#   python seed.py --demo      → ajoute aussi des données de démonstration
#   python seed.py --reset     → DROP toutes les tables puis recrée tout
# =============================================================================

import sys
import bcrypt
from datetime import datetime

from run import app
from app.models import (
    db, Secretariat, Etudiant, Enseignant, Classe, AnneeScolaire, Matiere,
    Inscription, Enseignement, EnseignementClasse, TypeNote, NoteEtudiant,
)
from app.utils.password import generer_mot_de_passe_etudiant, hasher_mot_de_passe


ADMIN_EMAIL = 'admin@ensea.ci'
ADMIN_PASSWORD = 'Admin@ENSEA2025'


def creer_admin():
    """Crée le compte secrétariat par défaut s'il n'existe pas déjà."""
    existant = Secretariat.query.filter_by(email=ADMIN_EMAIL).first()
    if existant:
        print(f'[=] Compte admin déjà présent : {ADMIN_EMAIL}')
        return existant

    admin = Secretariat(
        nom='ENSEA',
        prenom='Administrateur',
        email=ADMIN_EMAIL,
        mot_de_passe=hasher_mot_de_passe(ADMIN_PASSWORD),
    )
    db.session.add(admin)
    db.session.commit()
    print(f'[OK] Compte admin créé : {ADMIN_EMAIL} / {ADMIN_PASSWORD}')
    return admin


def creer_donnees_demo():
    """Insère un jeu de données minimal pour tester l'application."""
    admin = Secretariat.query.filter_by(email=ADMIN_EMAIL).first()

    # ── Années scolaires ──────────────────────────────────────────────────
    annees = {}
    for libelle in ['2024-2025', '2025-2026']:
        if not AnneeScolaire.query.filter_by(libelle=libelle).first():
            a = AnneeScolaire(libelle=libelle)
            db.session.add(a)
            annees[libelle] = a
    db.session.commit()
    annees = {a.libelle: a for a in AnneeScolaire.query.all()}

    # ── Classes ───────────────────────────────────────────────────────────
    classes = {}
    for nom in ['ISE1', 'ISE2', 'AS1', 'INFO1']:
        if not Classe.query.filter_by(nom=nom).first():
            c = Classe(nom=nom)
            db.session.add(c)
    db.session.commit()
    classes = {c.nom: c for c in Classe.query.all()}

    # ── Matières ──────────────────────────────────────────────────────────
    for nom in ['Statistiques', 'Mathématiques', 'Informatique', 'Économétrie',
                'Probabilités', 'Anglais']:
        if not Matiere.query.filter_by(nom=nom).first():
            db.session.add(Matiere(nom=nom))
    db.session.commit()
    matieres = {m.nom: m for m in Matiere.query.all()}

    # ── Enseignants ───────────────────────────────────────────────────────
    enseignants_demo = [
        ('KOUAME', 'Jean',    'jean.kouame@ensea.ci'),
        ('DIALLO', 'Aïcha',   'aicha.diallo@ensea.ci'),
        ('TRAORE', 'Issa',    'issa.traore@ensea.ci'),
    ]
    for nom, prenom, email in enseignants_demo:
        if not Enseignant.query.filter_by(email=email).first():
            db.session.add(Enseignant(
                nom=nom, prenom=prenom, email=email,
                enregistre_par_id=admin.id,
            ))
    db.session.commit()

    # ── Étudiants démo (compte rapide) ────────────────────────────────────
    if Etudiant.query.count() == 0:
        mdp_clairs = []
        for nom, prenom, email in [
            ('YAO',    'Koffi',   'koffi.yao@etu.ensea.ci'),
            ('BAMBA',  'Awa',     'awa.bamba@etu.ensea.ci'),
            ('OUATTARA', 'Sekou', 'sekou.ouattara@etu.ensea.ci'),
        ]:
            mdp_clair, mdp_hash = generer_mot_de_passe_etudiant(mdp_clairs)
            mdp_clairs.append(mdp_clair)
            etu = Etudiant(
                nom=nom, prenom=prenom, email=email,
                mot_de_passe_hash=mdp_hash, cree_par_id=admin.id,
            )
            db.session.add(etu)
            db.session.flush()
            db.session.add(Inscription(
                etudiant_id=etu.id,
                classe_id=classes['ISE1'].id,
                annee_scolaire_id=annees['2025-2026'].id,
                cree_par_id=admin.id,
            ))
            print(f'  [demo] Étudiant {email}  ->  mot de passe : {mdp_clair}')
        db.session.commit()

    print('[OK] Données de démonstration créées.')


def reset_db():
    """ATTENTION : supprime toutes les tables puis les recrée."""
    print('[!] DROP de toutes les tables ...')
    db.drop_all()
    print('[OK] Tables supprimées.')


def main():
    args = sys.argv[1:]

    with app.app_context():
        if '--reset' in args:
            reset_db()

        print('[..] Création des tables (si absentes) ...')
        db.create_all()
        print('[OK] Tables créées.')

        creer_admin()

        if '--demo' in args:
            print('[..] Insertion des données de démonstration ...')
            creer_donnees_demo()

        print('\n=== Initialisation terminée ===')
        print(f'Connectez-vous sur /auth/secretariat avec :')
        print(f'  Email    : {ADMIN_EMAIL}')
        print(f'  Mot de passe : {ADMIN_PASSWORD}')


if __name__ == '__main__':
    main()
