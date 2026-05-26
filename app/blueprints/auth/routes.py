# =============================================================================
# app/blueprints/auth/routes.py – Authentification (secrétariat + étudiant)
# =============================================================================

import secrets
from datetime import datetime

from flask import (
    render_template, redirect, url_for, request, flash, jsonify, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user

from app.models import (
    db, Secretariat, Etudiant, Inscription, Classe, AnneeScolaire,
    CodeReinit, valider_mot_de_passe,
)
from app.forms import (
    LoginSecretariatForm, LoginEtudiantForm, MotDePasseOublieForm,
    SaisieCodeForm,
)
from app.utils.password import (
    verifier_mot_de_passe, hasher_mot_de_passe, mot_de_passe_deja_utilise,
)
from app.utils.email_utils import envoyer_code_reset

from app.blueprints.auth import auth_bp


# ─────────────────────────────────────────────────────────────────────────────
# CHOIX DU RÔLE
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/')
def choisir_role():
    """Page d'accueil non connecté : redirige ou affiche le choix du rôle."""
    if current_user.is_authenticated:
        if current_user.role == 'secretariat':
            return redirect(url_for('secretariat.dashboard'))
        return redirect(url_for('etudiant.espace'))
    return render_template('auth/choisir_role.html')


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN SECRÉTARIAT
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/secretariat', methods=['GET', 'POST'])
def login_secretariat():
    if current_user.is_authenticated and current_user.role == 'secretariat':
        return redirect(url_for('secretariat.dashboard'))

    form = LoginSecretariatForm()
    if form.validate_on_submit():
        secret = Secretariat.query.filter_by(email=form.email.data.strip().lower()).first()
        if secret and verifier_mot_de_passe(form.mot_de_passe.data, secret.mot_de_passe):
            login_user(secret, remember=form.remember.data)
            flash(f'Bienvenue {secret.prenom} !', 'success')
            return redirect(request.args.get('next') or url_for('secretariat.dashboard'))
        flash('Email ou mot de passe incorrect.', 'danger')

    return render_template('auth/login_secretariat.html', form=form)


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN ÉTUDIANT (3 menus en cascade : année → classe → nom)
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/etudiant', methods=['GET', 'POST'])
def login_etudiant():
    if current_user.is_authenticated and current_user.role == 'etudiant':
        return redirect(url_for('etudiant.espace'))

    form = LoginEtudiantForm()

    # Population du menu années (les autres sont remplis dynamiquement via API)
    annees = AnneeScolaire.query.order_by(AnneeScolaire.libelle.desc()).all()
    form.annee_id.choices = [(0, '— Choisissez —')] + [(a.id, a.libelle) for a in annees]
    # Les choix classes et étudiants sont remplis côté JS, mais on doit fournir
    # un choix par défaut sinon WTForms rejette la validation.
    form.classe_id.choices   = [(0, '— Choisissez —')]
    form.etudiant_id.choices = [(0, '— Choisissez —')]

    # Pour valider correctement après POST, on remplit les choices avec la
    # valeur soumise (sinon WTForms la rejette comme "not a valid choice").
    if request.method == 'POST':
        a_id = request.form.get('annee_id', type=int) or 0
        c_id = request.form.get('classe_id', type=int) or 0
        e_id = request.form.get('etudiant_id', type=int) or 0
        if c_id:
            form.classe_id.choices.append((c_id, ''))
        if e_id:
            form.etudiant_id.choices.append((e_id, ''))

    if form.validate_on_submit():
        if not (form.annee_id.data and form.classe_id.data and form.etudiant_id.data):
            flash('Veuillez compléter tous les menus.', 'warning')
        else:
            # Vérifier que l'étudiant est bien inscrit dans cette classe + année
            insc = Inscription.query.filter_by(
                etudiant_id=form.etudiant_id.data,
                classe_id=form.classe_id.data,
                annee_scolaire_id=form.annee_id.data,
            ).first()
            if not insc:
                flash('Inscription introuvable pour ces critères.', 'danger')
            else:
                etu = Etudiant.query.get(form.etudiant_id.data)
                if etu and verifier_mot_de_passe(form.mot_de_passe.data, etu.mot_de_passe_hash):
                    login_user(etu)
                    flash(f'Bienvenue {etu.prenom} !', 'success')
                    return redirect(url_for('etudiant.espace'))
                flash('Mot de passe incorrect.', 'danger')

    return render_template('auth/login_etudiant.html', form=form)


# ─────────────────────────────────────────────────────────────────────────────
# API CASCADE (JSON)
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/api/classes/<int:annee_id>')
def api_classes(annee_id):
    """Classes ayant au moins une inscription pour l'année donnée."""
    classes = (
        db.session.query(Classe)
        .join(Inscription, Inscription.classe_id == Classe.id)
        .filter(Inscription.annee_scolaire_id == annee_id)
        .distinct()
        .order_by(Classe.nom)
        .all()
    )
    return jsonify([{'id': c.id, 'nom': c.nom} for c in classes])


@auth_bp.route('/api/etudiants/<int:annee_id>/<int:classe_id>')
def api_etudiants(annee_id, classe_id):
    """Étudiants inscrits dans (classe, année)."""
    etudiants = (
        db.session.query(Etudiant)
        .join(Inscription, Inscription.etudiant_id == Etudiant.id)
        .filter(
            Inscription.annee_scolaire_id == annee_id,
            Inscription.classe_id == classe_id,
        )
        .order_by(Etudiant.nom, Etudiant.prenom)
        .all()
    )
    return jsonify([
        {'id': e.id, 'nom_complet': e.nom_complet}
        for e in etudiants
    ])


# ─────────────────────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
@login_required
def logout():
    nom = current_user.prenom if hasattr(current_user, 'prenom') else ''
    logout_user()
    flash(f'À bientôt {nom} !', 'info')
    return redirect(url_for('auth.choisir_role'))


# ─────────────────────────────────────────────────────────────────────────────
# MOT DE PASSE OUBLIÉ (étudiant uniquement)
# ─────────────────────────────────────────────────────────────────────────────

@auth_bp.route('/mot-de-passe-oublie', methods=['GET', 'POST'])
def mot_de_passe_oublie():
    """Étape 1 : identification de l'étudiant + envoi du code par email."""
    form = MotDePasseOublieForm()

    annees = AnneeScolaire.query.order_by(AnneeScolaire.libelle.desc()).all()
    form.annee_id.choices    = [(0, '— Choisissez —')] + [(a.id, a.libelle) for a in annees]
    form.classe_id.choices   = [(0, '— Choisissez —')]
    form.etudiant_id.choices = [(0, '— Choisissez —')]

    if request.method == 'POST':
        c_id = request.form.get('classe_id', type=int) or 0
        e_id = request.form.get('etudiant_id', type=int) or 0
        if c_id:
            form.classe_id.choices.append((c_id, ''))
        if e_id:
            form.etudiant_id.choices.append((e_id, ''))

    if form.validate_on_submit() and form.etudiant_id.data:
        etu = Etudiant.query.get(form.etudiant_id.data)
        if not etu:
            flash('Étudiant introuvable.', 'danger')
        else:
            # Invalider les anciens codes non utilisés
            for c in etu.codes_reinit.filter_by(utilise=False).all():
                c.invalider()

            # Générer un code à 6 chiffres
            code = f'{secrets.randbelow(1_000_000):06d}'
            code_obj = CodeReinit.creer(etudiant_id=etu.id, code=code)
            db.session.add(code_obj)
            db.session.commit()

            envoyer_code_reset(etu, code)
            flash('Un code de vérification vous a été envoyé par email.', 'success')
            return redirect(url_for('auth.saisir_code', etudiant_id=etu.id))

    return render_template('auth/mot_de_passe_oublie.html', form=form)


@auth_bp.route('/saisir-code/<int:etudiant_id>', methods=['GET', 'POST'])
def saisir_code(etudiant_id):
    """Étape 2 : saisie du code + nouveau mot de passe."""
    etu = Etudiant.query.get_or_404(etudiant_id)
    form = SaisieCodeForm()

    if form.validate_on_submit():
        # Vérifier le code
        code_obj = (
            etu.codes_reinit
               .filter_by(code=form.code.data, utilise=False)
               .order_by(CodeReinit.date_creation.desc())
               .first()
        )
        if not code_obj or not code_obj.est_valide:
            flash('Code invalide ou expiré.', 'danger')
            return render_template('auth/saisir_code.html', form=form, etudiant=etu)

        # Vérifier l'unicité du nouveau mot de passe
        if mot_de_passe_deja_utilise(form.nouveau_mdp.data, ignorer_etudiant_id=etu.id):
            flash(
                'Ce mot de passe est déjà utilisé par un autre étudiant. '
                'Choisissez-en un autre.', 'danger',
            )
            return render_template('auth/saisir_code.html', form=form, etudiant=etu)

        # Réinitialiser
        etu.mot_de_passe_hash = hasher_mot_de_passe(form.nouveau_mdp.data)
        code_obj.invalider()
        db.session.commit()

        flash('Mot de passe réinitialisé avec succès. Vous pouvez vous connecter.', 'success')
        return redirect(url_for('auth.login_etudiant'))

    return render_template('auth/saisir_code.html', form=form, etudiant=etu)
