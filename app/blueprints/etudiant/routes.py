# =============================================================================
# app/blueprints/etudiant/routes.py – Espace étudiant
# =============================================================================

import os
from io import BytesIO
from datetime import datetime
from werkzeug.utils import secure_filename

from flask import (
    render_template, redirect, url_for, request, flash, send_file,
    current_app, abort, jsonify,
)
from flask_login import current_user

from app.models import (
    db, Etudiant, Inscription, Classe, AnneeScolaire, Matiere,
    Enseignement, EnseignementClasse, TypeNote, NoteEtudiant,
)
from app.forms import ChangementMotDePasseForm, ProfilEtudiantForm
from app.utils.password import (
    verifier_mot_de_passe, hasher_mot_de_passe, mot_de_passe_deja_utilise,
)
from app.utils.email_utils import envoyer_confirmation_changement
from app.utils.stats import stats_descriptives, calculer_rangs, moyenne_simple
from app.utils.pdf import releve_notes_etudiant
from app.utils.excel import dataframe_vers_excel_bytes

from app.blueprints.etudiant import etudiant_bp, etudiant_required


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _annees_etudiant(etudiant_id: int) -> list[AnneeScolaire]:
    """Renvoie la liste des années auxquelles l'étudiant est inscrit."""
    return (
        db.session.query(AnneeScolaire)
        .join(Inscription, Inscription.annee_scolaire_id == AnneeScolaire.id)
        .filter(Inscription.etudiant_id == etudiant_id)
        .order_by(AnneeScolaire.libelle.desc())
        .distinct()
        .all()
    )


def _matieres_pour_etudiant(etudiant: Etudiant, annee_id: int) -> list[dict]:
    """Renvoie pour chaque matière enseignée dans la classe/année de l'étudiant :
       - moyenne perso, mention, rang, comparaison classe.
    """
    insc = Inscription.query.filter_by(
        etudiant_id=etudiant.id, annee_scolaire_id=annee_id,
    ).first()
    if not insc:
        return []

    # Tous les EnseignementClasse pour la classe + année
    enseignements = (
        db.session.query(Enseignement, EnseignementClasse, Matiere)
        .join(EnseignementClasse, EnseignementClasse.enseignement_id == Enseignement.id)
        .join(Matiere,            Matiere.id == Enseignement.matiere_id)
        .filter(
            EnseignementClasse.classe_id == insc.classe_id,
            Enseignement.annee_scolaire_id == annee_id,
        )
        .order_by(Matiere.nom)
        .all()
    )

    resultat = []
    for ens, ec, mat in enseignements:
        # Tous les types de note pour cet EnseignementClasse
        types = TypeNote.query.filter_by(ens_classe_id=ec.id).all()
        if not types:
            resultat.append({
                'enseignement_id': ens.id, 'ec_id': ec.id,
                'matiere': mat.nom,
                'moyenne': None, 'moyenne_classe': None,
                'rang': None, 'effectif': 0,
                'notes_dispo': False, 'nb_notes': 0,
            })
            continue

        # Moyenne perso : moyenne arithmétique des notes existantes (sur tous types)
        notes_perso = []
        for t in types:
            n = NoteEtudiant.query.filter_by(
                type_note_id=t.id, etudiant_id=etudiant.id,
            ).first()
            if n is not None:
                notes_perso.append(float(n.valeur))

        # Moyenne de chaque étudiant de la classe sur ces types (pour rang)
        # On agrège : pour chaque étudiant ayant au moins 1 note, sa moyenne
        notes_classe_par_etu: dict[int, list] = {}
        for t in types:
            for n in NoteEtudiant.query.filter_by(type_note_id=t.id).all():
                notes_classe_par_etu.setdefault(n.etudiant_id, []).append(float(n.valeur))
        moyennes_classe = {
            eid: sum(v) / len(v) for eid, v in notes_classe_par_etu.items() if v
        }

        moyenne_perso = sum(notes_perso) / len(notes_perso) if notes_perso else None
        moyenne_classe = (
            sum(moyennes_classe.values()) / len(moyennes_classe)
            if moyennes_classe else None
        )
        rangs = calculer_rangs(moyennes_classe)
        rang = rangs.get(etudiant.id)
        effectif = len(moyennes_classe)

        resultat.append({
            'enseignement_id': ens.id,
            'ec_id': ec.id,
            'matiere': mat.nom,
            'moyenne': round(moyenne_perso, 2) if moyenne_perso is not None else None,
            'moyenne_classe': round(moyenne_classe, 2) if moyenne_classe is not None else None,
            'rang': rang,
            'effectif': effectif,
            'notes_dispo': bool(notes_perso),
            'nb_notes': len(notes_perso),
            'nb_types': len(types),
        })

    return resultat


def _detail_matiere(etudiant: Etudiant, ec_id: int) -> dict:
    """Détail d'une matière pour l'étudiant : table des types de note avec
    comparaison classe, courbe de progression."""
    ec = EnseignementClasse.query.get_or_404(ec_id)

    # Vérification que l'étudiant est bien inscrit dans la classe + année
    insc = Inscription.query.filter_by(
        etudiant_id=etudiant.id,
        classe_id=ec.classe_id,
        annee_scolaire_id=ec.enseignement.annee_scolaire_id,
    ).first()
    if not insc:
        abort(403)

    types = (
        TypeNote.query.filter_by(ens_classe_id=ec_id)
        .order_by(TypeNote.date_creation, TypeNote.id)
        .all()
    )

    detail = []
    courbe_labels = []
    courbe_perso = []
    courbe_classe = []

    for t in types:
        # Note perso
        note_perso = NoteEtudiant.query.filter_by(
            type_note_id=t.id, etudiant_id=etudiant.id,
        ).first()
        # Toutes les notes classe pour ce type
        toutes = [
            float(n.valeur)
            for n in NoteEtudiant.query.filter_by(type_note_id=t.id).all()
        ]
        st = stats_descriptives(toutes)

        detail.append({
            'libelle': t.libelle,
            'note_perso': float(note_perso.valeur) if note_perso else None,
            **st,
        })

        courbe_labels.append(t.libelle)
        courbe_perso.append(float(note_perso.valeur) if note_perso else None)
        courbe_classe.append(st['moyenne'])

    return {
        'ec': ec,
        'matiere':    ec.enseignement.matiere,
        'enseignant': ec.enseignement.enseignant,
        'classe':     ec.classe,
        'annee':      ec.enseignement.annee_scolaire,
        'types':      detail,
        'courbe_labels': courbe_labels,
        'courbe_perso':  courbe_perso,
        'courbe_classe': courbe_classe,
        'a_notes':       any(d['note_perso'] is not None for d in detail),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ESPACE ÉTUDIANT (vue principale)
# ─────────────────────────────────────────────────────────────────────────────

@etudiant_bp.route('/')
@etudiant_required
def espace():
    """Vue principale : sélection de l'année + matières avec moyennes/rangs."""
    annees = _annees_etudiant(current_user.id)
    if not annees:
        return render_template('etudiant/espace.html',
                                annees=[], annee_courante=None, matieres=[])

    # Année sélectionnée : par query string sinon la plus récente
    annee_id = request.args.get('annee_id', type=int) or annees[0].id
    annee = AnneeScolaire.query.get(annee_id)
    if annee not in annees:
        annee = annees[0]

    matieres = _matieres_pour_etudiant(current_user, annee.id)

    return render_template(
        'etudiant/espace.html',
        annees=annees, annee_courante=annee, matieres=matieres,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DÉTAIL D'UNE MATIÈRE
# ─────────────────────────────────────────────────────────────────────────────

@etudiant_bp.route('/matiere/<int:ec_id>')
@etudiant_required
def matiere_detail(ec_id):
    detail = _detail_matiere(current_user, ec_id)
    return render_template('etudiant/matiere_detail.html', **detail)


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT DU RELEVÉ DE NOTES
# ─────────────────────────────────────────────────────────────────────────────

@etudiant_bp.route('/releve.pdf')
@etudiant_required
def releve_pdf():
    annee_id = request.args.get('annee_id', type=int)
    annees = _annees_etudiant(current_user.id)
    annee  = next((a for a in annees if a.id == annee_id), annees[0] if annees else None)
    if not annee:
        flash('Aucune année trouvée.', 'warning')
        return redirect(url_for('etudiant.espace'))

    matieres = _matieres_pour_etudiant(current_user, annee.id)

    # Détail pour le PDF (notes par matière)
    donnees = []
    for m in matieres:
        d = _detail_matiere(current_user, m['ec_id'])
        notes_simples = [
            {
                'libelle': t['libelle'],
                'note':    t['note_perso'],
                'moyenne_classe': t['moyenne'],
            }
            for t in d['types']
        ]
        # Mention
        mention = ''
        if m['moyenne'] is not None:
            v = m['moyenne']
            if   v >= 16: mention = 'Très Bien'
            elif v >= 14: mention = 'Bien'
            elif v >= 12: mention = 'Assez Bien'
            elif v >= 10: mention = 'Passable'
            else:         mention = 'Insuffisant'

        donnees.append({
            'matiere':  m['matiere'],
            'moyenne':  m['moyenne'],
            'mention':  mention,
            'rang':     m['rang'],
            'effectif': m['effectif'],
            'notes':    notes_simples,
        })

    pdf_bytes = releve_notes_etudiant(current_user, annee.libelle, donnees)
    return send_file(
        BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=f'releve_{current_user.nom}_{annee.libelle}.pdf',
        mimetype='application/pdf',
    )


@etudiant_bp.route('/releve.xlsx')
@etudiant_required
def releve_excel():
    import pandas as pd
    annee_id = request.args.get('annee_id', type=int)
    annees = _annees_etudiant(current_user.id)
    annee  = next((a for a in annees if a.id == annee_id), annees[0] if annees else None)
    if not annee:
        flash('Aucune année trouvée.', 'warning')
        return redirect(url_for('etudiant.espace'))

    matieres = _matieres_pour_etudiant(current_user, annee.id)
    lignes = []
    for m in matieres:
        d = _detail_matiere(current_user, m['ec_id'])
        for t in d['types']:
            lignes.append({
                'Matière':         m['matiere'],
                'Évaluation':      t['libelle'],
                'Note':            t['note_perso'] if t['note_perso'] is not None else '',
                'Moyenne classe':  t['moyenne']    if t['moyenne']    is not None else '',
                'Effectif':        t['effectif'],
            })

    df = pd.DataFrame(lignes)
    data = dataframe_vers_excel_bytes(df, nom_feuille=annee.libelle)
    return send_file(
        BytesIO(data),
        as_attachment=True,
        download_name=f'releve_{current_user.nom}_{annee.libelle}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROFIL
# ─────────────────────────────────────────────────────────────────────────────

@etudiant_bp.route('/profil', methods=['GET', 'POST'])
@etudiant_required
def profil():
    form = ProfilEtudiantForm()

    if form.validate_on_submit() and form.photo.data:
        f = form.photo.data
        ext = os.path.splitext(secure_filename(f.filename))[1].lower()
        nom = f'etu_{current_user.id}{ext}'
        dossier = os.path.join(current_app.static_folder, 'photos')
        os.makedirs(dossier, exist_ok=True)
        chemin = os.path.join(dossier, nom)
        f.save(chemin)
        current_user.photo = f'photos/{nom}'
        db.session.commit()
        flash('Photo de profil mise à jour.', 'success')
        return redirect(url_for('etudiant.profil'))

    return render_template('etudiant/profil.html', form=form)


@etudiant_bp.route('/profil/mot-de-passe', methods=['GET', 'POST'])
@etudiant_required
def changer_mot_de_passe():
    form = ChangementMotDePasseForm()
    if form.validate_on_submit():
        if not verifier_mot_de_passe(form.ancien_mdp.data, current_user.mot_de_passe_hash):
            flash('Ancien mot de passe incorrect.', 'danger')
        elif mot_de_passe_deja_utilise(form.nouveau_mdp.data,
                                        ignorer_etudiant_id=current_user.id):
            flash(
                'Ce mot de passe est déjà utilisé par un autre étudiant. '
                'Choisissez-en un autre.', 'danger',
            )
        else:
            current_user.mot_de_passe_hash = hasher_mot_de_passe(form.nouveau_mdp.data)
            db.session.commit()
            envoyer_confirmation_changement(
                current_user, datetime.now().strftime('%d/%m/%Y à %Hh%M'),
            )
            flash('Mot de passe modifié avec succès.', 'success')
            return redirect(url_for('etudiant.profil'))
    return render_template('etudiant/changer_mdp.html', form=form)
