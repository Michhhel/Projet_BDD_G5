# =============================================================================
# app/blueprints/secretariat/routes.py – Routes principales secrétariat
# =============================================================================
# Pour la lisibilité, les routes sont regroupées par domaine fonctionnel mais
# toutes dans le même fichier (~12 sections).
# =============================================================================

from datetime import datetime, date, timedelta
from io import BytesIO

from flask import (
    render_template, redirect, url_for, request, flash, jsonify, send_file,
    abort, current_app,
)
from sqlalchemy import func, or_

from app.models import (
    db, Secretariat, Etudiant, Enseignant, Classe, AnneeScolaire, Matiere,
    Inscription, Enseignement, EnseignementClasse, TypeNote, NoteEtudiant,
)
from app.forms import (
    AnneeForm, ClasseForm, MatiereForm, EnseignantForm, EnseignementForm,
    EnseignementClasseForm, EtudiantForm, EtudiantEditionForm,
    TypeNoteForm, TypeNoteEditionForm, ImportEnseignantsForm,
    ImportEtudiantsForm, ImportNotesForm, SecretariatForm,
    SecretariatEditionForm, ActionForm,
)
from app.utils.password import (
    generer_mot_de_passe_etudiant, hasher_mot_de_passe,
    mot_de_passe_deja_utilise,
)
from app.utils.email_utils import (
    envoyer_nouveau_compte, envoyer_nouveau_mot_de_passe,
)
from app.utils.excel import (
    lire_fichier, valider_colonnes, normaliser_colonnes, previsualisation,
    dataframe_vers_excel_bytes, plusieurs_dataframes_vers_excel,
    queryset_vers_dataframe,
)
from app.utils.stats import (
    stats_descriptives, calculer_rangs, histogramme_bins,
    repartition_mentions, moyenne_simple,
)
from app.utils.annee import valider_libelle_annee
from app.utils.pdf import bulletin_classe

from app.blueprints.secretariat import secretariat_bp, secretariat_required


# =============================================================================
# DASHBOARD
# =============================================================================

@secretariat_bp.route('/dashboard')
@secretariat_required
def dashboard():
    """Tableau de bord : cartes + graphiques + activité récente + alertes."""
    stats = {
        'etudiants':    Etudiant.query.count(),
        'enseignants':  Enseignant.query.count(),
        'classes':      Classe.query.count(),
        'matieres':     Matiere.query.count(),
        'annees':       AnneeScolaire.query.count(),
        'notes':        NoteEtudiant.query.count(),
        'enseignements': Enseignement.query.count(),
    }

    # Inscriptions par année (barres)
    # NB : on convertit les Row SQLAlchemy en tuples Python pour la sérialisation JSON
    insc_par_annee = [
        (libelle, int(n))
        for libelle, n in (
            db.session.query(AnneeScolaire.libelle, func.count(Inscription.id))
            .outerjoin(Inscription, Inscription.annee_scolaire_id == AnneeScolaire.id)
            .group_by(AnneeScolaire.libelle)
            .order_by(AnneeScolaire.libelle)
            .all()
        )
    ]

    # Moyennes par matière (toutes années confondues)
    moyennes_par_matiere = [
        (nom, float(avg) if avg is not None else 0)
        for nom, avg in (
            db.session.query(Matiere.nom, func.avg(NoteEtudiant.valeur))
            .join(TypeNote,            TypeNote.id == NoteEtudiant.type_note_id)
            .join(EnseignementClasse,  EnseignementClasse.id == TypeNote.ens_classe_id)
            .join(Enseignement,        Enseignement.id == EnseignementClasse.enseignement_id)
            .join(Matiere,             Matiere.id == Enseignement.matiere_id)
            .group_by(Matiere.nom)
            .order_by(Matiere.nom)
            .all()
        )
    ]

    # Activité récente : 5 dernières notes modifiées
    notes_recentes = (
        db.session.query(NoteEtudiant)
        .order_by(NoteEtudiant.date_modification.desc())
        .limit(5)
        .all()
    )

    # ── Alertes ──────────────────────────────────────────────────────────
    # 1. Classes sans enseignement
    classes_sans_ens = (
        db.session.query(Classe)
        .outerjoin(EnseignementClasse, EnseignementClasse.classe_id == Classe.id)
        .filter(EnseignementClasse.id.is_(None))
        .all()
    )
    # 2. Étudiants sans note depuis +30 jours (et qui ont au moins 1 note)
    seuil = datetime.utcnow() - timedelta(days=30)
    etudiants_inactifs = (
        db.session.query(Etudiant)
        .join(NoteEtudiant, NoteEtudiant.etudiant_id == Etudiant.id)
        .group_by(Etudiant.id)
        .having(func.max(NoteEtudiant.date_modification) < seuil)
        .limit(10)
        .all()
    )

    return render_template(
        'secretariat/dashboard.html',
        stats=stats,
        insc_par_annee=insc_par_annee,
        moyennes_par_matiere=moyennes_par_matiere,
        notes_recentes=notes_recentes,
        classes_sans_ens=classes_sans_ens,
        etudiants_inactifs=etudiants_inactifs,
    )


# =============================================================================
# ANNÉES SCOLAIRES
# =============================================================================

@secretariat_bp.route('/annees', methods=['GET', 'POST'])
@secretariat_required
def annees():
    form = AnneeForm()
    action_form = ActionForm()

    if form.validate_on_submit():
        libelle = form.libelle.data.strip()
        ok, msg = valider_libelle_annee(libelle)
        if not ok:
            flash(msg, 'danger')
        elif AnneeScolaire.query.filter_by(libelle=libelle).first():
            flash(f"L'année « {libelle} » existe déjà.", 'warning')
        else:
            db.session.add(AnneeScolaire(libelle=libelle))
            db.session.commit()
            flash(f"Année « {libelle} » créée.", 'success')
            return redirect(url_for('secretariat.annees'))

    annees_list = AnneeScolaire.query.order_by(AnneeScolaire.libelle.desc()).all()
    # Stats par année pour affichage rapide
    stats_par_annee = {}
    for a in annees_list:
        stats_par_annee[a.id] = {
            'inscriptions':  a.inscriptions.count(),
            'enseignements': a.enseignements.count(),
        }

    return render_template(
        'secretariat/annees.html',
        form=form, action_form=action_form,
        annees=annees_list, stats=stats_par_annee,
    )


@secretariat_bp.route('/annees/<int:annee_id>/modifier', methods=['POST'])
@secretariat_required
def modifier_annee(annee_id):
    annee = AnneeScolaire.query.get_or_404(annee_id)
    nouveau = (request.form.get('libelle') or '').strip()
    ok, msg = valider_libelle_annee(nouveau)
    if not ok:
        flash(msg, 'danger')
    elif AnneeScolaire.query.filter(AnneeScolaire.libelle == nouveau,
                                     AnneeScolaire.id != annee_id).first():
        flash(f"L'année « {nouveau } » existe déjà.", 'warning')
    else:
        annee.libelle = nouveau
        db.session.commit()
        flash('Année modifiée.', 'success')
    return redirect(url_for('secretariat.annees'))


@secretariat_bp.route('/annees/<int:annee_id>/supprimer', methods=['POST'])
@secretariat_required
def supprimer_annee(annee_id):
    annee = AnneeScolaire.query.get_or_404(annee_id)
    if annee.inscriptions.count() > 0 or annee.enseignements.count() > 0:
        flash(
            f"Impossible de supprimer « {annee.libelle} » : "
            f"{annee.inscriptions.count()} inscription(s) et "
            f"{annee.enseignements.count()} enseignement(s) y sont liés.",
            'danger',
        )
    else:
        db.session.delete(annee)
        db.session.commit()
        flash(f"Année « {annee.libelle} » supprimée.", 'success')
    return redirect(url_for('secretariat.annees'))


# =============================================================================
# CLASSES
# =============================================================================

@secretariat_bp.route('/classes', methods=['GET', 'POST'])
@secretariat_required
def classes():
    form = ClasseForm()
    action_form = ActionForm()

    if form.validate_on_submit():
        nom = form.nom.data.strip()
        if Classe.query.filter_by(nom=nom).first():
            flash(f"La classe « {nom} » existe déjà.", 'warning')
        else:
            db.session.add(Classe(nom=nom))
            db.session.commit()
            flash(f"Classe « {nom} » créée.", 'success')
            return redirect(url_for('secretariat.classes'))

    classes_list = Classe.query.order_by(Classe.nom).all()
    stats = {
        c.id: {
            'inscriptions':       c.inscriptions.count(),
            'enseignement_classes': c.enseignement_classes.count(),
        }
        for c in classes_list
    }
    return render_template(
        'secretariat/classes.html',
        form=form, action_form=action_form,
        classes=classes_list, stats=stats,
    )


@secretariat_bp.route('/classes/<int:classe_id>/modifier', methods=['POST'])
@secretariat_required
def modifier_classe(classe_id):
    classe = Classe.query.get_or_404(classe_id)
    nouveau = (request.form.get('nom') or '').strip()
    if not nouveau:
        flash('Nom obligatoire.', 'danger')
    elif Classe.query.filter(Classe.nom == nouveau, Classe.id != classe_id).first():
        flash(f"Une classe « {nouveau} » existe déjà.", 'warning')
    else:
        classe.nom = nouveau
        db.session.commit()
        flash('Classe renommée.', 'success')
    return redirect(url_for('secretariat.classes'))


@secretariat_bp.route('/classes/<int:classe_id>/supprimer', methods=['POST'])
@secretariat_required
def supprimer_classe(classe_id):
    classe = Classe.query.get_or_404(classe_id)
    if classe.inscriptions.count() > 0 or classe.enseignement_classes.count() > 0:
        flash(
            f"Impossible de supprimer « {classe.nom} » : "
            f"{classe.inscriptions.count()} inscription(s) et "
            f"{classe.enseignement_classes.count()} enseignement(s) y sont liés.",
            'danger',
        )
    else:
        db.session.delete(classe)
        db.session.commit()
        flash(f"Classe « {classe.nom} » supprimée.", 'success')
    return redirect(url_for('secretariat.classes'))


@secretariat_bp.route('/classes/<int:classe_id>/matieres')
@secretariat_required
def matieres_de_classe(classe_id):
    """Affiche les matières enseignées dans une classe (via EnseignementClasse)."""
    classe = Classe.query.get_or_404(classe_id)
    enseignements = (
        db.session.query(Enseignement, Matiere, Enseignant, AnneeScolaire)
        .join(EnseignementClasse, EnseignementClasse.enseignement_id == Enseignement.id)
        .join(Matiere,            Matiere.id == Enseignement.matiere_id)
        .join(Enseignant,         Enseignant.id == Enseignement.enseignant_id)
        .join(AnneeScolaire,      AnneeScolaire.id == Enseignement.annee_scolaire_id)
        .filter(EnseignementClasse.classe_id == classe_id)
        .order_by(AnneeScolaire.libelle.desc(), Matiere.nom)
        .all()
    )
    return render_template(
        'secretariat/classe_detail.html',
        classe=classe, enseignements=enseignements,
    )


# =============================================================================
# MATIÈRES
# =============================================================================

@secretariat_bp.route('/matieres', methods=['GET', 'POST'])
@secretariat_required
def matieres():
    form = MatiereForm()
    action_form = ActionForm()

    if form.validate_on_submit():
        nom = form.nom.data.strip()
        if Matiere.query.filter(func.lower(Matiere.nom) == nom.lower()).first():
            flash(f"La matière « {nom} » existe déjà.", 'warning')
        else:
            db.session.add(Matiere(nom=nom))
            db.session.commit()
            flash(f"Matière « {nom} » créée.", 'success')
            return redirect(url_for('secretariat.matieres'))

    matieres_list = Matiere.query.order_by(Matiere.nom).all()
    stats = {m.id: {'enseignements': m.enseignements.count()} for m in matieres_list}
    return render_template(
        'secretariat/matieres.html',
        form=form, action_form=action_form,
        matieres=matieres_list, stats=stats,
    )


@secretariat_bp.route('/matieres/<int:matiere_id>/modifier', methods=['POST'])
@secretariat_required
def modifier_matiere(matiere_id):
    matiere = Matiere.query.get_or_404(matiere_id)
    nouveau = (request.form.get('nom') or '').strip()
    if not nouveau:
        flash('Nom obligatoire.', 'danger')
    else:
        matiere.nom = nouveau
        db.session.commit()
        flash('Matière modifiée.', 'success')
    return redirect(url_for('secretariat.matieres'))


@secretariat_bp.route('/matieres/<int:matiere_id>/supprimer', methods=['POST'])
@secretariat_required
def supprimer_matiere(matiere_id):
    matiere = Matiere.query.get_or_404(matiere_id)
    if matiere.enseignements.count() > 0:
        flash(
            f"Impossible de supprimer « {matiere.nom} » : "
            f"{matiere.enseignements.count()} enseignement(s) y sont liés.",
            'danger',
        )
    else:
        db.session.delete(matiere)
        db.session.commit()
        flash(f"Matière « {matiere.nom} » supprimée.", 'success')
    return redirect(url_for('secretariat.matieres'))


# =============================================================================
# ENSEIGNANTS
# =============================================================================

@secretariat_bp.route('/enseignants', methods=['GET', 'POST'])
@secretariat_required
def enseignants():
    form = EnseignantForm()
    import_form = ImportEnseignantsForm()
    action_form = ActionForm()
    from flask_login import current_user

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Enseignant.query.filter_by(email=email).first():
            flash(f'Un enseignant avec l\'email « {email} » existe déjà.', 'warning')
        else:
            db.session.add(Enseignant(
                nom=form.nom.data.strip().upper(),
                prenom=form.prenom.data.strip(),
                email=email,
                enregistre_par_id=current_user.id,
            ))
            db.session.commit()
            flash('Enseignant ajouté.', 'success')
            return redirect(url_for('secretariat.enseignants'))

    enseignants_list = Enseignant.query.order_by(Enseignant.nom, Enseignant.prenom).all()
    return render_template(
        'secretariat/enseignants.html',
        form=form, import_form=import_form, action_form=action_form,
        enseignants=enseignants_list,
    )


@secretariat_bp.route('/enseignants/<int:ens_id>/modifier', methods=['POST'])
@secretariat_required
def modifier_enseignant(ens_id):
    ens = Enseignant.query.get_or_404(ens_id)
    nom    = (request.form.get('nom') or '').strip().upper()
    prenom = (request.form.get('prenom') or '').strip()
    email  = (request.form.get('email') or '').strip().lower()

    if not (nom and prenom and email):
        flash('Tous les champs sont obligatoires.', 'danger')
    elif Enseignant.query.filter(Enseignant.email == email, Enseignant.id != ens_id).first():
        flash(f"L'email « {email} » est déjà utilisé.", 'warning')
    else:
        ens.nom = nom; ens.prenom = prenom; ens.email = email
        db.session.commit()
        flash('Enseignant modifié.', 'success')
    return redirect(url_for('secretariat.enseignants'))


@secretariat_bp.route('/enseignants/<int:ens_id>/supprimer', methods=['POST'])
@secretariat_required
def supprimer_enseignant(ens_id):
    ens = Enseignant.query.get_or_404(ens_id)
    if ens.enseignements.count() > 0:
        flash(
            f"Impossible de supprimer {ens.nom_complet} : "
            f"{ens.enseignements.count()} enseignement(s) liés.",
            'danger',
        )
    else:
        db.session.delete(ens)
        db.session.commit()
        flash(f'{ens.nom_complet} supprimé.', 'success')
    return redirect(url_for('secretariat.enseignants'))


@secretariat_bp.route('/enseignants/import', methods=['POST'])
@secretariat_required
def importer_enseignants():
    from flask_login import current_user
    form = ImportEnseignantsForm()
    if not form.validate_on_submit():
        flash('Fichier manquant ou invalide.', 'danger')
        return redirect(url_for('secretariat.enseignants'))

    try:
        df = lire_fichier(form.fichier.data)
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('secretariat.enseignants'))

    df = normaliser_colonnes(df)
    manquantes = valider_colonnes(df, ['nom', 'prenom', 'email'])
    if manquantes:
        flash(f"Colonnes manquantes : {', '.join(manquantes)}", 'danger')
        return redirect(url_for('secretariat.enseignants'))

    crees, ignores, erreurs = 0, 0, []
    for idx, row in df.iterrows():
        try:
            email = str(row['email']).strip().lower()
            if not email or '@' not in email:
                erreurs.append(f'Ligne {idx + 2} : email invalide')
                continue
            if Enseignant.query.filter_by(email=email).first():
                ignores += 1
                continue
            db.session.add(Enseignant(
                nom=str(row['nom']).strip().upper(),
                prenom=str(row['prenom']).strip(),
                email=email,
                enregistre_par_id=current_user.id,
            ))
            crees += 1
        except Exception as exc:
            erreurs.append(f'Ligne {idx + 2} : {exc}')

    db.session.commit()
    flash(
        f'Import terminé : {crees} créé(s), {ignores} ignoré(s) (doublons), '
        f'{len(erreurs)} erreur(s).',
        'success' if crees else 'warning',
    )
    if erreurs:
        flash('Erreurs : ' + ' / '.join(erreurs[:5]), 'danger')
    return redirect(url_for('secretariat.enseignants'))


# =============================================================================
# ENSEIGNEMENTS
# =============================================================================

@secretariat_bp.route('/enseignements', methods=['GET', 'POST'])
@secretariat_required
def enseignements():
    from flask_login import current_user
    form = EnseignementForm()
    action_form = ActionForm()
    ec_form = EnseignementClasseForm()

    form.enseignant_id.choices = [
        (e.id, e.nom_complet)
        for e in Enseignant.query.order_by(Enseignant.nom).all()
    ]
    form.matiere_id.choices = [
        (m.id, m.nom) for m in Matiere.query.order_by(Matiere.nom).all()
    ]
    form.annee_scolaire_id.choices = [
        (a.id, a.libelle)
        for a in AnneeScolaire.query.order_by(AnneeScolaire.libelle.desc()).all()
    ]

    if form.validate_on_submit():
        existe = Enseignement.query.filter_by(
            enseignant_id=form.enseignant_id.data,
            matiere_id=form.matiere_id.data,
            annee_scolaire_id=form.annee_scolaire_id.data,
        ).first()
        if existe:
            flash('Cet enseignement existe déjà.', 'warning')
        else:
            db.session.add(Enseignement(
                enseignant_id=form.enseignant_id.data,
                matiere_id=form.matiere_id.data,
                annee_scolaire_id=form.annee_scolaire_id.data,
                configure_par_id=current_user.id,
            ))
            db.session.commit()
            flash('Enseignement créé.', 'success')
            return redirect(url_for('secretariat.enseignements'))

    enseignements_list = (
        db.session.query(Enseignement)
        .join(AnneeScolaire, AnneeScolaire.id == Enseignement.annee_scolaire_id)
        .order_by(AnneeScolaire.libelle.desc(), Enseignement.id.desc())
        .all()
    )
    toutes_classes = Classe.query.order_by(Classe.nom).all()

    return render_template(
        'secretariat/enseignements.html',
        form=form, action_form=action_form, ec_form=ec_form,
        enseignements=enseignements_list,
        toutes_classes=toutes_classes,
    )


@secretariat_bp.route('/enseignements/<int:ens_id>/modifier', methods=['POST'])
@secretariat_required
def modifier_enseignement(ens_id):
    ens = Enseignement.query.get_or_404(ens_id)
    ens.enseignant_id     = request.form.get('enseignant_id', type=int)
    ens.matiere_id        = request.form.get('matiere_id', type=int)
    ens.annee_scolaire_id = request.form.get('annee_scolaire_id', type=int)
    try:
        db.session.commit()
        flash('Enseignement modifié.', 'success')
    except Exception:
        db.session.rollback()
        flash('Erreur : combinaison déjà existante ou invalide.', 'danger')
    return redirect(url_for('secretariat.enseignements'))


@secretariat_bp.route('/enseignements/<int:ens_id>/supprimer', methods=['POST'])
@secretariat_required
def supprimer_enseignement(ens_id):
    ens = Enseignement.query.get_or_404(ens_id)
    # Vérifier qu'aucune note n'est attachée via les TypeNote
    notes_count = (
        db.session.query(func.count(NoteEtudiant.id))
        .join(TypeNote, TypeNote.id == NoteEtudiant.type_note_id)
        .join(EnseignementClasse, EnseignementClasse.id == TypeNote.ens_classe_id)
        .filter(EnseignementClasse.enseignement_id == ens_id)
        .scalar()
    )
    if notes_count > 0:
        flash(
            f'Impossible de supprimer : {notes_count} note(s) saisie(s) sur cet enseignement.',
            'danger',
        )
    else:
        db.session.delete(ens)
        db.session.commit()
        flash('Enseignement supprimé.', 'success')
    return redirect(url_for('secretariat.enseignements'))


@secretariat_bp.route('/enseignements/<int:ens_id>/ajouter-classe', methods=['POST'])
@secretariat_required
def ajouter_classe_a_enseignement(ens_id):
    Enseignement.query.get_or_404(ens_id)
    classe_id = request.form.get('classe_id', type=int)
    if not classe_id:
        flash('Classe manquante.', 'danger')
        return redirect(url_for('secretariat.enseignements'))
    if EnseignementClasse.query.filter_by(enseignement_id=ens_id, classe_id=classe_id).first():
        flash('Cette classe est déjà associée.', 'warning')
    else:
        db.session.add(EnseignementClasse(enseignement_id=ens_id, classe_id=classe_id))
        db.session.commit()
        flash('Classe associée.', 'success')
    return redirect(url_for('secretariat.enseignements'))


@secretariat_bp.route('/enseignement-classes/<int:ec_id>/retirer', methods=['POST'])
@secretariat_required
def retirer_classe_enseignement(ec_id):
    ec = EnseignementClasse.query.get_or_404(ec_id)
    # Empêcher si des notes existent
    notes_count = (
        db.session.query(func.count(NoteEtudiant.id))
        .join(TypeNote, TypeNote.id == NoteEtudiant.type_note_id)
        .filter(TypeNote.ens_classe_id == ec_id)
        .scalar()
    )
    if notes_count > 0:
        flash(f'Impossible : {notes_count} note(s) saisie(s) sur cette classe.', 'danger')
    else:
        db.session.delete(ec)
        db.session.commit()
        flash('Classe retirée de l\'enseignement.', 'success')
    return redirect(url_for('secretariat.enseignements'))


# =============================================================================
# ÉTUDIANTS
# =============================================================================

@secretariat_bp.route('/etudiants', methods=['GET', 'POST'])
@secretariat_required
def etudiants():
    from flask_login import current_user
    form = EtudiantForm()
    import_form = ImportEtudiantsForm()
    action_form = ActionForm()

    # Population des selects
    annees_choices  = [(a.id, a.libelle) for a in
                       AnneeScolaire.query.order_by(AnneeScolaire.libelle.desc()).all()]
    classes_choices = [(c.id, c.nom) for c in
                       Classe.query.order_by(Classe.nom).all()]
    form.annee_scolaire_id.choices       = annees_choices
    form.classe_id.choices               = classes_choices
    import_form.annee_scolaire_id.choices = annees_choices
    import_form.classe_id.choices         = classes_choices

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Etudiant.query.filter_by(email=email).first():
            flash(f"L'email « {email} » est déjà utilisé.", 'warning')
        else:
            mdp_clair, mdp_hash = generer_mot_de_passe_etudiant()
            etu = Etudiant(
                nom=form.nom.data.strip().upper(),
                prenom=form.prenom.data.strip(),
                email=email,
                mot_de_passe_hash=mdp_hash,
                cree_par_id=current_user.id,
            )
            db.session.add(etu)
            db.session.flush()
            db.session.add(Inscription(
                etudiant_id=etu.id,
                classe_id=form.classe_id.data,
                annee_scolaire_id=form.annee_scolaire_id.data,
                cree_par_id=current_user.id,
            ))
            db.session.commit()

            envoyer_nouveau_compte(
                etu, mdp_clair,
                url_connexion=url_for('auth.login_etudiant', _external=True),
            )
            flash(
                f'Étudiant créé. Mot de passe envoyé à {etu.email} '
                f'(ou affiché en console en dev).', 'success',
            )
            return redirect(url_for('secretariat.etudiants'))

    # ── Filtres GET ──────────────────────────────────────────────────────
    f_annee  = request.args.get('annee_id',  type=int)
    f_classe = request.args.get('classe_id', type=int)
    q = (
        db.session.query(Etudiant, Classe, AnneeScolaire)
        .join(Inscription,    Inscription.etudiant_id == Etudiant.id)
        .join(Classe,         Classe.id == Inscription.classe_id)
        .join(AnneeScolaire,  AnneeScolaire.id == Inscription.annee_scolaire_id)
    )
    if f_annee:
        q = q.filter(Inscription.annee_scolaire_id == f_annee)
    if f_classe:
        q = q.filter(Inscription.classe_id == f_classe)
    etudiants_list = q.order_by(Etudiant.nom, Etudiant.prenom).all()

    return render_template(
        'secretariat/etudiants.html',
        form=form, import_form=import_form, action_form=action_form,
        etudiants=etudiants_list,
        annees=AnneeScolaire.query.order_by(AnneeScolaire.libelle.desc()).all(),
        classes=Classe.query.order_by(Classe.nom).all(),
        f_annee=f_annee, f_classe=f_classe,
    )


@secretariat_bp.route('/etudiants/<int:etu_id>/modifier', methods=['POST'])
@secretariat_required
def modifier_etudiant(etu_id):
    etu = Etudiant.query.get_or_404(etu_id)
    nom    = (request.form.get('nom') or '').strip().upper()
    prenom = (request.form.get('prenom') or '').strip()
    email  = (request.form.get('email') or '').strip().lower()

    if not (nom and prenom and email):
        flash('Tous les champs sont obligatoires.', 'danger')
    elif Etudiant.query.filter(Etudiant.email == email, Etudiant.id != etu_id).first():
        flash(f"L'email « {email} » est déjà utilisé.", 'warning')
    else:
        etu.nom = nom; etu.prenom = prenom; etu.email = email
        db.session.commit()
        flash('Étudiant modifié.', 'success')
    return redirect(url_for('secretariat.etudiants'))


@secretariat_bp.route('/etudiants/<int:etu_id>/supprimer', methods=['POST'])
@secretariat_required
def supprimer_etudiant(etu_id):
    etu = Etudiant.query.get_or_404(etu_id)
    if etu.notes.count() > 0:
        flash(
            f"Impossible de supprimer {etu.nom_complet} : "
            f"{etu.notes.count()} note(s) attachée(s).",
            'danger',
        )
    else:
        nom = etu.nom_complet
        db.session.delete(etu)
        db.session.commit()
        flash(f'{nom} supprimé.', 'success')
    return redirect(url_for('secretariat.etudiants'))


@secretariat_bp.route('/etudiants/<int:etu_id>/reset-mdp', methods=['POST'])
@secretariat_required
def reset_mdp_etudiant(etu_id):
    etu = Etudiant.query.get_or_404(etu_id)
    mdp_clair, mdp_hash = generer_mot_de_passe_etudiant()
    etu.mot_de_passe_hash = mdp_hash
    db.session.commit()
    envoyer_nouveau_mot_de_passe(etu, mdp_clair)
    flash(
        f'Mot de passe réinitialisé. Nouveau mot de passe : {mdp_clair} '
        f'(également envoyé par email).', 'success',
    )
    return redirect(url_for('secretariat.etudiants'))


@secretariat_bp.route('/etudiants/import', methods=['POST'])
@secretariat_required
def importer_etudiants():
    from flask_login import current_user
    form = ImportEtudiantsForm()
    form.annee_scolaire_id.choices = [(a.id, a.libelle) for a in AnneeScolaire.query.all()]
    form.classe_id.choices         = [(c.id, c.nom) for c in Classe.query.all()]

    if not form.validate_on_submit():
        flash('Données du formulaire invalides.', 'danger')
        return redirect(url_for('secretariat.etudiants'))

    try:
        df = lire_fichier(form.fichier.data)
    except ValueError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('secretariat.etudiants'))

    df = normaliser_colonnes(df)
    manquantes = valider_colonnes(df, ['nom', 'prenom', 'email'])
    if manquantes:
        flash(f"Colonnes manquantes : {', '.join(manquantes)}", 'danger')
        return redirect(url_for('secretariat.etudiants'))

    crees, ignores, erreurs = 0, 0, []
    mdp_clairs_generes: list[str] = []

    for idx, row in df.iterrows():
        try:
            email = str(row['email']).strip().lower()
            if not email or '@' not in email:
                erreurs.append(f'Ligne {idx + 2} : email invalide')
                continue
            if Etudiant.query.filter_by(email=email).first():
                ignores += 1
                continue
            mdp_clair, mdp_hash = generer_mot_de_passe_etudiant(mdp_clairs_generes)
            mdp_clairs_generes.append(mdp_clair)

            etu = Etudiant(
                nom=str(row['nom']).strip().upper(),
                prenom=str(row['prenom']).strip(),
                email=email,
                mot_de_passe_hash=mdp_hash,
                cree_par_id=current_user.id,
            )
            db.session.add(etu)
            db.session.flush()
            db.session.add(Inscription(
                etudiant_id=etu.id,
                classe_id=form.classe_id.data,
                annee_scolaire_id=form.annee_scolaire_id.data,
                cree_par_id=current_user.id,
            ))
            envoyer_nouveau_compte(
                etu, mdp_clair,
                url_connexion=url_for('auth.login_etudiant', _external=True),
            )
            crees += 1
        except Exception as exc:
            erreurs.append(f'Ligne {idx + 2} : {exc}')

    db.session.commit()
    flash(
        f'Import : {crees} créé(s), {ignores} ignoré(s) (doublons), '
        f'{len(erreurs)} erreur(s).',
        'success' if crees else 'warning',
    )
    if erreurs:
        flash('Erreurs : ' + ' / '.join(erreurs[:5]), 'danger')
    return redirect(url_for('secretariat.etudiants'))


# =============================================================================
# TYPES DE NOTE
# =============================================================================

@secretariat_bp.route('/types-note', methods=['GET', 'POST'])
@secretariat_required
def types_note():
    from flask_login import current_user
    form = TypeNoteForm()
    action_form = ActionForm()

    # Choix EnseignementClasse : libellé "Matière — Classe (Année)"
    ec_choices = []
    for ec in (
        db.session.query(EnseignementClasse, Enseignement, Matiere, Classe, AnneeScolaire)
        .join(Enseignement,   Enseignement.id == EnseignementClasse.enseignement_id)
        .join(Matiere,        Matiere.id == Enseignement.matiere_id)
        .join(Classe,         Classe.id == EnseignementClasse.classe_id)
        .join(AnneeScolaire,  AnneeScolaire.id == Enseignement.annee_scolaire_id)
        .order_by(AnneeScolaire.libelle.desc(), Matiere.nom, Classe.nom)
        .all()
    ):
        ec_obj, ens, mat, cls, ann = ec
        ec_choices.append((ec_obj.id, f'{mat.nom} — {cls.nom} ({ann.libelle})'))
    form.ens_classe_id.choices = ec_choices

    if form.validate_on_submit():
        existant = TypeNote.query.filter_by(
            ens_classe_id=form.ens_classe_id.data,
            libelle=form.libelle.data.strip(),
        ).first()
        if existant:
            flash('Ce type de note existe déjà pour cet enseignement.', 'warning')
        else:
            db.session.add(TypeNote(
                ens_classe_id=form.ens_classe_id.data,
                libelle=form.libelle.data.strip(),
                charge_par_id=current_user.id,
            ))
            db.session.commit()
            flash('Type de note créé.', 'success')
            return redirect(url_for('secretariat.types_note'))

    types_list = (
        db.session.query(TypeNote, EnseignementClasse, Matiere, Classe, AnneeScolaire)
        .join(EnseignementClasse, EnseignementClasse.id == TypeNote.ens_classe_id)
        .join(Enseignement,       Enseignement.id == EnseignementClasse.enseignement_id)
        .join(Matiere,            Matiere.id == Enseignement.matiere_id)
        .join(Classe,             Classe.id == EnseignementClasse.classe_id)
        .join(AnneeScolaire,      AnneeScolaire.id == Enseignement.annee_scolaire_id)
        .order_by(AnneeScolaire.libelle.desc(), Matiere.nom, Classe.nom, TypeNote.libelle)
        .all()
    )
    return render_template(
        'secretariat/types_note.html',
        form=form, action_form=action_form, types=types_list,
    )


@secretariat_bp.route('/types-note/<int:tn_id>/modifier', methods=['POST'])
@secretariat_required
def modifier_type_note(tn_id):
    tn = TypeNote.query.get_or_404(tn_id)
    nouveau = (request.form.get('libelle') or '').strip()
    if not nouveau:
        flash('Libellé obligatoire.', 'danger')
    else:
        tn.libelle = nouveau
        try:
            db.session.commit()
            flash('Type de note modifié.', 'success')
        except Exception:
            db.session.rollback()
            flash('Libellé déjà utilisé pour cet enseignement.', 'danger')
    return redirect(url_for('secretariat.types_note'))


@secretariat_bp.route('/types-note/<int:tn_id>/supprimer', methods=['POST'])
@secretariat_required
def supprimer_type_note(tn_id):
    tn = TypeNote.query.get_or_404(tn_id)
    if tn.notes_etudiants.count() > 0:
        flash(
            f'Impossible : {tn.notes_etudiants.count()} note(s) saisie(s) pour ce type.',
            'danger',
        )
    else:
        db.session.delete(tn)
        db.session.commit()
        flash('Type de note supprimé.', 'success')
    return redirect(url_for('secretariat.types_note'))


# ─────────────────────────────────────────────────────────────────────────────
# API pour la cascade import_notes (ens_classe -> types disponibles)
# ─────────────────────────────────────────────────────────────────────────────

@secretariat_bp.route('/api/types-note/<int:ec_id>')
@secretariat_required
def api_types_note(ec_id):
    types = TypeNote.query.filter_by(ens_classe_id=ec_id).order_by(TypeNote.libelle).all()
    return jsonify([{'id': t.id, 'libelle': t.libelle} for t in types])


# =============================================================================
# IMPORT NOTES
# =============================================================================

@secretariat_bp.route('/notes/import', methods=['GET', 'POST'])
@secretariat_required
def import_notes():
    form = ImportNotesForm()

    # Liste des EnseignementClasse pour le select
    ec_choices = []
    for ec, ens, mat, cls, ann in (
        db.session.query(EnseignementClasse, Enseignement, Matiere, Classe, AnneeScolaire)
        .join(Enseignement,  Enseignement.id == EnseignementClasse.enseignement_id)
        .join(Matiere,       Matiere.id == Enseignement.matiere_id)
        .join(Classe,        Classe.id == EnseignementClasse.classe_id)
        .join(AnneeScolaire, AnneeScolaire.id == Enseignement.annee_scolaire_id)
        .order_by(AnneeScolaire.libelle.desc(), Matiere.nom, Classe.nom)
        .all()
    ):
        ec_choices.append((ec.id, f'{mat.nom} — {cls.nom} ({ann.libelle})'))
    form.ens_classe_id.choices = ec_choices
    # Le sélecteur de type est rempli dynamiquement via API ; on doit fournir
    # au moins un choix par défaut pour la validation initiale
    form.type_note_id.choices = [(0, '— Sélectionnez d\'abord un enseignement —')]
    # Pour pouvoir valider après soumission, on accepte la valeur soumise
    if request.method == 'POST':
        tn_id = request.form.get('type_note_id', type=int) or 0
        if tn_id:
            form.type_note_id.choices.append((tn_id, ''))

    rapport = None

    if form.validate_on_submit() and form.type_note_id.data:
        try:
            df = lire_fichier(form.fichier.data)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return redirect(url_for('secretariat.import_notes'))

        df = normaliser_colonnes(df)
        manquantes = valider_colonnes(df, ['email', 'note'])
        if manquantes:
            flash(f"Colonnes manquantes : {', '.join(manquantes)}", 'danger')
            return redirect(url_for('secretariat.import_notes'))

        type_note = TypeNote.query.get_or_404(form.type_note_id.data)

        crees, mis_a_jour, erreurs = 0, 0, []
        for idx, row in df.iterrows():
            try:
                email = str(row['email']).strip().lower()
                if not email:
                    erreurs.append(f'Ligne {idx + 2} : email vide')
                    continue
                etu = Etudiant.query.filter_by(email=email).first()
                if not etu:
                    erreurs.append(f'Ligne {idx + 2} : email « {email} » introuvable')
                    continue

                # Conversion + validation valeur
                val_str = str(row['note']).replace(',', '.').strip()
                try:
                    val = float(val_str)
                except ValueError:
                    erreurs.append(f'Ligne {idx + 2} : note « {row["note"]} » non numérique')
                    continue
                if val < 0 or val > 20:
                    erreurs.append(f'Ligne {idx + 2} : note {val} hors [0,20]')
                    continue

                existante = NoteEtudiant.query.filter_by(
                    type_note_id=type_note.id,
                    etudiant_id=etu.id,
                ).first()
                if existante:
                    existante.valeur = val  # UPDATE, pas DELETE
                    mis_a_jour += 1
                else:
                    db.session.add(NoteEtudiant(
                        type_note_id=type_note.id,
                        etudiant_id=etu.id,
                        valeur=val,
                    ))
                    crees += 1
            except Exception as exc:
                erreurs.append(f'Ligne {idx + 2} : {exc}')

        db.session.commit()
        rapport = {
            'crees': crees, 'mis_a_jour': mis_a_jour,
            'erreurs': erreurs, 'total': len(df),
            'type_note': type_note,
        }
        flash(
            f'Import terminé : {crees} créé(s), {mis_a_jour} mis à jour, '
            f'{len(erreurs)} erreur(s).',
            'success' if (crees or mis_a_jour) else 'warning',
        )

    return render_template('secretariat/import_notes.html', form=form, rapport=rapport)


# ─────────────────────────────────────────────────────────────────────────────
# Prévisualisation Excel (avant import)
# ─────────────────────────────────────────────────────────────────────────────

@secretariat_bp.route('/notes/previsualiser', methods=['POST'])
@secretariat_required
def previsualiser_notes():
    """Renvoie en JSON les 5 premières lignes du fichier (pour confirmation)."""
    f = request.files.get('fichier')
    if not f:
        return jsonify({'erreur': 'Fichier manquant.'}), 400
    try:
        df = lire_fichier(f)
    except ValueError as exc:
        return jsonify({'erreur': str(exc)}), 400
    df = normaliser_colonnes(df)
    return jsonify({
        'colonnes': list(df.columns),
        'lignes':   previsualisation(df, 5),
        'total':    int(len(df)),
    })


# =============================================================================
# VISUALISATION DES NOTES
# =============================================================================

@secretariat_bp.route('/notes/visualiser')
@secretariat_required
def visualiser_notes():
    """Visualisation avec filtres dynamiques + stats + graphiques."""
    annee_id   = request.args.get('annee_id',  type=int)
    classe_id  = request.args.get('classe_id', type=int)
    matiere_id = request.args.get('matiere_id', type=int)
    tn_id      = request.args.get('type_note_id', type=int)

    annees    = AnneeScolaire.query.order_by(AnneeScolaire.libelle.desc()).all()
    classes_l = Classe.query.order_by(Classe.nom).all()
    matieres  = Matiere.query.order_by(Matiere.nom).all()

    # Type de note disponibles selon les filtres
    tn_query = (
        db.session.query(TypeNote, EnseignementClasse, Enseignement)
        .join(EnseignementClasse, EnseignementClasse.id == TypeNote.ens_classe_id)
        .join(Enseignement,       Enseignement.id == EnseignementClasse.enseignement_id)
    )
    if annee_id:
        tn_query = tn_query.filter(Enseignement.annee_scolaire_id == annee_id)
    if classe_id:
        tn_query = tn_query.filter(EnseignementClasse.classe_id == classe_id)
    if matiere_id:
        tn_query = tn_query.filter(Enseignement.matiere_id == matiere_id)

    types_dispo = [t[0] for t in tn_query.order_by(TypeNote.libelle).all()]

    contexte = {
        'annees': annees, 'classes': classes_l, 'matieres': matieres,
        'types_dispo': types_dispo,
        'annee_id': annee_id, 'classe_id': classe_id,
        'matiere_id': matiere_id, 'tn_id': tn_id,
        'stats': None, 'notes_etudiants': None,
        'histo_labels': [], 'histo_data': [],
        'mention_labels': [], 'mention_data': [],
        'type_note': None,
    }

    if tn_id:
        type_note = TypeNote.query.get_or_404(tn_id)
        notes_q = (
            db.session.query(NoteEtudiant, Etudiant)
            .join(Etudiant, Etudiant.id == NoteEtudiant.etudiant_id)
            .filter(NoteEtudiant.type_note_id == tn_id)
            .order_by(NoteEtudiant.valeur.desc())
            .all()
        )
        valeurs = [float(n.valeur) for n, _ in notes_q]
        stats = stats_descriptives(valeurs)

        # Rangs
        rangs = calculer_rangs({etu.id: float(n.valeur) for n, etu in notes_q})

        # Histogramme + mentions
        h_labels, h_data = histogramme_bins(valeurs, nb_bins=10)
        m_dict = repartition_mentions(valeurs)

        contexte.update({
            'type_note': type_note,
            'stats': stats,
            'notes_etudiants': [
                {
                    'etudiant': etu,
                    'note': float(n.valeur),
                    'rang': rangs.get(etu.id),
                }
                for n, etu in notes_q
            ],
            'histo_labels':   h_labels,
            'histo_data':     h_data,
            'mention_labels': list(m_dict.keys()),
            'mention_data':   list(m_dict.values()),
        })

    return render_template('secretariat/visualiser_notes.html', **contexte)


# ─────────────────────────────────────────────────────────────────────────────
# Export Excel des notes filtrées
# ─────────────────────────────────────────────────────────────────────────────

@secretariat_bp.route('/notes/export-excel')
@secretariat_required
def export_notes_excel():
    tn_id = request.args.get('type_note_id', type=int)
    if not tn_id:
        flash('Sélectionnez un type de note avant d\'exporter.', 'warning')
        return redirect(url_for('secretariat.visualiser_notes'))

    tn = TypeNote.query.get_or_404(tn_id)
    notes_q = (
        db.session.query(NoteEtudiant, Etudiant)
        .join(Etudiant, Etudiant.id == NoteEtudiant.etudiant_id)
        .filter(NoteEtudiant.type_note_id == tn_id)
        .order_by(NoteEtudiant.valeur.desc())
        .all()
    )
    rangs = calculer_rangs({etu.id: float(n.valeur) for n, etu in notes_q})

    import pandas as pd
    df = pd.DataFrame([
        {
            'Nom':    etu.nom,
            'Prénom': etu.prenom,
            'Email':  etu.email,
            'Note':   float(n.valeur),
            'Rang':   rangs.get(etu.id),
        }
        for n, etu in notes_q
    ])
    data = dataframe_vers_excel_bytes(df, nom_feuille=tn.libelle[:31])
    return send_file(
        BytesIO(data),
        as_attachment=True,
        download_name=f'notes_{tn.libelle}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@secretariat_bp.route('/notes/export-pdf')
@secretariat_required
def export_notes_pdf():
    tn_id = request.args.get('type_note_id', type=int)
    if not tn_id:
        flash('Sélectionnez un type de note avant d\'exporter.', 'warning')
        return redirect(url_for('secretariat.visualiser_notes'))

    tn = TypeNote.query.get_or_404(tn_id)
    ec = tn.enseignement_classe
    ens = ec.enseignement
    mat = ens.matiere
    cls = ec.classe
    ann = ens.annee_scolaire

    notes_q = (
        db.session.query(NoteEtudiant, Etudiant)
        .join(Etudiant, Etudiant.id == NoteEtudiant.etudiant_id)
        .filter(NoteEtudiant.type_note_id == tn_id)
        .order_by(NoteEtudiant.valeur.desc())
        .all()
    )
    valeurs = [float(n.valeur) for n, _ in notes_q]
    rangs   = calculer_rangs({etu.id: float(n.valeur) for n, etu in notes_q})
    stats   = stats_descriptives(valeurs)

    lignes = [
        [str(rangs.get(etu.id, '-')), etu.nom, etu.prenom, f'{float(n.valeur):.2f}']
        for n, etu in notes_q
    ]
    pdf_bytes = bulletin_classe(
        titre=f'Notes — {mat.nom}',
        sous_titre=f'{cls.nom} — {ann.libelle} — {tn.libelle}',
        en_tetes=['Rang', 'Nom', 'Prénom', 'Note /20'],
        lignes=lignes,
        stats={
            'Effectif':    stats['effectif'],
            'Moyenne':     stats['moyenne'],
            'Médiane':     stats['mediane'],
            'Min / Max':   f"{stats['min']} / {stats['max']}",
            'Q1 / Q3':     f"{stats['q1']} / {stats['q3']}",
            'Écart-type':  stats['ecart_type'],
        },
    )
    return send_file(
        BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=f'bulletin_{cls.nom}_{mat.nom}_{tn.libelle}.pdf',
        mimetype='application/pdf',
    )


# =============================================================================
# EXPORT GLOBAL (toutes les tables)
# =============================================================================

@secretariat_bp.route('/exports')
@secretariat_required
def exports():
    """Page récapitulative avec liens d'export par table."""
    return render_template('secretariat/exports.html')


@secretariat_bp.route('/exports/global')
@secretariat_required
def export_global():
    """Génère un fichier Excel multi-onglets avec toutes les tables."""
    import pandas as pd
    dfs = {
        'Secretariat': queryset_vers_dataframe(
            Secretariat.query.all(),
            [('ID', 'id'), ('Nom', 'nom'), ('Prénom', 'prenom'), ('Email', 'email')],
        ),
        'Etudiants': queryset_vers_dataframe(
            Etudiant.query.all(),
            [('ID', 'id'), ('Nom', 'nom'), ('Prénom', 'prenom'), ('Email', 'email')],
        ),
        'Enseignants': queryset_vers_dataframe(
            Enseignant.query.all(),
            [('ID', 'id'), ('Nom', 'nom'), ('Prénom', 'prenom'), ('Email', 'email')],
        ),
        'Classes':  queryset_vers_dataframe(
            Classe.query.all(), [('ID', 'id'), ('Nom', 'nom')],
        ),
        'Annees':   queryset_vers_dataframe(
            AnneeScolaire.query.all(), [('ID', 'id'), ('Libellé', 'libelle')],
        ),
        'Matieres': queryset_vers_dataframe(
            Matiere.query.all(), [('ID', 'id'), ('Nom', 'nom')],
        ),
        'Inscriptions': queryset_vers_dataframe(
            Inscription.query.all(),
            [
                ('ID', 'id'),
                ('Étudiant', lambda i: Etudiant.query.get(i.etudiant_id).nom_complet
                                       if i.etudiant_id else ''),
                ('Classe',   lambda i: Classe.query.get(i.classe_id).nom if i.classe_id else ''),
                ('Année',    lambda i: AnneeScolaire.query.get(i.annee_scolaire_id).libelle
                                       if i.annee_scolaire_id else ''),
                ('Date',     'date_inscription'),
            ],
        ),
        'Enseignements': queryset_vers_dataframe(
            Enseignement.query.all(),
            [
                ('ID', 'id'),
                ('Enseignant', lambda e: e.enseignant.nom_complet if e.enseignant else ''),
                ('Matière',    lambda e: e.matiere.nom if e.matiere else ''),
                ('Année',      lambda e: e.annee_scolaire.libelle if e.annee_scolaire else ''),
            ],
        ),
        'Notes': queryset_vers_dataframe(
            NoteEtudiant.query.all(),
            [
                ('ID', 'id'),
                ('Étudiant', lambda n: n.etudiant.nom_complet if n.etudiant else ''),
                ('Type',     lambda n: n.type_note.libelle if n.type_note else ''),
                ('Valeur',   'valeur'),
                ('Date saisie', 'date_saisie'),
                ('Date modif',  'date_modification'),
            ],
        ),
    }
    data = plusieurs_dataframes_vers_excel(dfs)
    return send_file(
        BytesIO(data),
        as_attachment=True,
        download_name=f'ensea_export_{date.today().isoformat()}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


# =============================================================================
# COMPTES SECRÉTARIAT
# =============================================================================

@secretariat_bp.route('/comptes', methods=['GET', 'POST'])
@secretariat_required
def comptes_secretariat():
    form = SecretariatForm()
    action_form = ActionForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if Secretariat.query.filter_by(email=email).first():
            flash(f"L'email « {email} » est déjà utilisé.", 'warning')
        else:
            from app.utils.password import hasher_mot_de_passe
            db.session.add(Secretariat(
                nom=form.nom.data.strip().upper(),
                prenom=form.prenom.data.strip(),
                email=email,
                mot_de_passe=hasher_mot_de_passe(form.mot_de_passe.data),
            ))
            db.session.commit()
            flash('Compte secrétariat créé.', 'success')
            return redirect(url_for('secretariat.comptes_secretariat'))

    comptes = Secretariat.query.order_by(Secretariat.nom, Secretariat.prenom).all()
    return render_template(
        'secretariat/comptes.html',
        form=form, action_form=action_form, comptes=comptes,
    )


@secretariat_bp.route('/comptes/<int:s_id>/modifier', methods=['POST'])
@secretariat_required
def modifier_compte_secretariat(s_id):
    s = Secretariat.query.get_or_404(s_id)
    nom    = (request.form.get('nom') or '').strip().upper()
    prenom = (request.form.get('prenom') or '').strip()
    email  = (request.form.get('email') or '').strip().lower()
    if not (nom and prenom and email):
        flash('Tous les champs sont obligatoires.', 'danger')
    elif Secretariat.query.filter(Secretariat.email == email,
                                   Secretariat.id != s_id).first():
        flash(f"L'email « {email} » est déjà utilisé.", 'warning')
    else:
        s.nom = nom; s.prenom = prenom; s.email = email
        db.session.commit()
        flash('Compte modifié.', 'success')
    return redirect(url_for('secretariat.comptes_secretariat'))


@secretariat_bp.route('/comptes/<int:s_id>/supprimer', methods=['POST'])
@secretariat_required
def supprimer_compte_secretariat(s_id):
    from flask_login import current_user
    if s_id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte.', 'danger')
        return redirect(url_for('secretariat.comptes_secretariat'))
    s = Secretariat.query.get_or_404(s_id)
    if Secretariat.query.count() <= 1:
        flash('Impossible de supprimer le dernier compte secrétariat.', 'danger')
    else:
        nom = s.nom_complet
        db.session.delete(s)
        db.session.commit()
        flash(f'{nom} supprimé.', 'success')
    return redirect(url_for('secretariat.comptes_secretariat'))


# =============================================================================
# CONSULTATION DES NOTES D'UN ÉTUDIANT (côté secrétariat)
# =============================================================================

@secretariat_bp.route('/etudiants/<int:etu_id>/notes')
@secretariat_required
def notes_etudiant(etu_id):
    """Affiche toutes les notes d'un étudiant (avec stats classe)."""
    etu = Etudiant.query.get_or_404(etu_id)

    notes_q = (
        db.session.query(NoteEtudiant, TypeNote, EnseignementClasse, Matiere, Classe, AnneeScolaire)
        .join(TypeNote,           TypeNote.id == NoteEtudiant.type_note_id)
        .join(EnseignementClasse, EnseignementClasse.id == TypeNote.ens_classe_id)
        .join(Enseignement,       Enseignement.id == EnseignementClasse.enseignement_id)
        .join(Matiere,            Matiere.id == Enseignement.matiere_id)
        .join(Classe,             Classe.id == EnseignementClasse.classe_id)
        .join(AnneeScolaire,      AnneeScolaire.id == Enseignement.annee_scolaire_id)
        .filter(NoteEtudiant.etudiant_id == etu_id)
        .order_by(AnneeScolaire.libelle.desc(), Matiere.nom, TypeNote.libelle)
        .all()
    )

    # Pour chaque note, moyenne de la classe sur le même type_note
    notes_detail = []
    for n, tn, ec, mat, cls, ann in notes_q:
        toutes = [
            float(x.valeur)
            for x in NoteEtudiant.query.filter_by(type_note_id=tn.id).all()
        ]
        notes_detail.append({
            'note':    float(n.valeur),
            'libelle': tn.libelle,
            'matiere': mat.nom,
            'classe':  cls.nom,
            'annee':   ann.libelle,
            'moyenne_classe': moyenne_simple(toutes),
            'effectif': len(toutes),
        })

    return render_template(
        'secretariat/etudiant_notes.html',
        etudiant=etu, notes=notes_detail,
    )
