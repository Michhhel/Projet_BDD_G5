# =============================================================================
# app/forms.py – Tous les formulaires Flask-WTF de l'application ENSEA
# =============================================================================

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, PasswordField, BooleanField, SelectField, IntegerField,
    DecimalField, TextAreaField, SubmitField, HiddenField,
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, NumberRange, Optional, ValidationError,
    Regexp,
)

from app.models import valider_mot_de_passe


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTIFICATION
# ─────────────────────────────────────────────────────────────────────────────

class LoginSecretariatForm(FlaskForm):
    email        = StringField('Email', validators=[
        DataRequired(message='Email requis.'),
        Email(message='Format email invalide.'),
        Length(max=100),
    ])
    mot_de_passe = PasswordField('Mot de passe', validators=[
        DataRequired(message='Mot de passe requis.'),
    ])
    remember     = BooleanField('Se souvenir de moi')
    submit       = SubmitField('Se connecter')


class LoginEtudiantForm(FlaskForm):
    annee_id      = SelectField('Année scolaire', coerce=int,
                                 validators=[DataRequired(message='Sélectionnez une année.')])
    classe_id     = SelectField('Classe', coerce=int,
                                 validators=[DataRequired(message='Sélectionnez une classe.')])
    etudiant_id   = SelectField('Nom complet', coerce=int,
                                 validators=[DataRequired(message='Sélectionnez votre nom.')])
    mot_de_passe  = PasswordField('Mot de passe', validators=[
        DataRequired(message='Mot de passe requis.'),
    ])
    submit        = SubmitField('Se connecter')


class MotDePasseOublieForm(FlaskForm):
    annee_id    = SelectField('Année scolaire', coerce=int,
                               validators=[DataRequired()])
    classe_id   = SelectField('Classe', coerce=int,
                               validators=[DataRequired()])
    etudiant_id = SelectField('Nom complet', coerce=int,
                               validators=[DataRequired()])
    submit      = SubmitField('Recevoir un code par email')


class SaisieCodeForm(FlaskForm):
    code               = StringField('Code reçu (6 chiffres)', validators=[
        DataRequired(),
        Regexp(r'^\d{6}$', message='Le code doit comporter 6 chiffres.'),
    ])
    nouveau_mdp        = PasswordField('Nouveau mot de passe', validators=[
        DataRequired(),
        Length(min=8, message='8 caractères minimum.'),
    ])
    confirmation       = PasswordField('Confirmation', validators=[
        DataRequired(),
        EqualTo('nouveau_mdp', message='Les mots de passe ne correspondent pas.'),
    ])
    submit             = SubmitField('Réinitialiser le mot de passe')

    def validate_nouveau_mdp(self, field):
        if not valider_mot_de_passe(field.data):
            raise ValidationError(
                'Le mot de passe doit contenir 8 caractères minimum, 1 majuscule, '
                '1 minuscule, 1 chiffre et un caractère spécial parmi : - . _ @ + *'
            )


class ChangementMotDePasseForm(FlaskForm):
    ancien_mdp    = PasswordField('Ancien mot de passe', validators=[DataRequired()])
    nouveau_mdp   = PasswordField('Nouveau mot de passe', validators=[
        DataRequired(),
        Length(min=8),
    ])
    confirmation  = PasswordField('Confirmation', validators=[
        DataRequired(),
        EqualTo('nouveau_mdp', message='Les mots de passe ne correspondent pas.'),
    ])
    submit        = SubmitField('Changer le mot de passe')

    def validate_nouveau_mdp(self, field):
        if not valider_mot_de_passe(field.data):
            raise ValidationError(
                '8 car. min, 1 majuscule, 1 minuscule, 1 chiffre, 1 spécial parmi - . _ @ + *'
            )


# ─────────────────────────────────────────────────────────────────────────────
# SECRÉTARIAT — GESTION DES RÉFÉRENTIELS
# ─────────────────────────────────────────────────────────────────────────────

class AnneeForm(FlaskForm):
    libelle = StringField('Libellé', validators=[
        DataRequired(),
        Length(min=9, max=20),
        Regexp(r'^\d{4}-\d{4}$', message='Format attendu : YYYY-YYYY (ex. 2025-2026).'),
    ])
    submit  = SubmitField('Enregistrer')


class ClasseForm(FlaskForm):
    nom    = StringField('Nom de la classe', validators=[
        DataRequired(),
        Length(min=1, max=50),
    ])
    submit = SubmitField('Enregistrer')


class MatiereForm(FlaskForm):
    nom    = StringField('Nom de la matière', validators=[
        DataRequired(),
        Length(min=1, max=100),
    ])
    submit = SubmitField('Enregistrer')


class EnseignantForm(FlaskForm):
    nom    = StringField('Nom', validators=[DataRequired(), Length(max=50)])
    prenom = StringField('Prénom', validators=[DataRequired(), Length(max=50)])
    email  = StringField('Email', validators=[
        DataRequired(), Email(), Length(max=100),
    ])
    submit = SubmitField('Enregistrer')


class EnseignementForm(FlaskForm):
    enseignant_id     = SelectField('Enseignant', coerce=int, validators=[DataRequired()])
    matiere_id        = SelectField('Matière', coerce=int, validators=[DataRequired()])
    annee_scolaire_id = SelectField('Année scolaire', coerce=int, validators=[DataRequired()])
    submit            = SubmitField('Enregistrer')


class EnseignementClasseForm(FlaskForm):
    """Ajout d'une classe à un enseignement existant."""
    classe_id = SelectField('Classe', coerce=int, validators=[DataRequired()])
    submit    = SubmitField('Ajouter')


# ─────────────────────────────────────────────────────────────────────────────
# ÉTUDIANTS
# ─────────────────────────────────────────────────────────────────────────────

class EtudiantForm(FlaskForm):
    nom               = StringField('Nom', validators=[DataRequired(), Length(max=50)])
    prenom            = StringField('Prénom', validators=[DataRequired(), Length(max=50)])
    email             = StringField('Email', validators=[
        DataRequired(), Email(), Length(max=100),
    ])
    annee_scolaire_id = SelectField('Année scolaire', coerce=int, validators=[DataRequired()])
    classe_id         = SelectField('Classe', coerce=int, validators=[DataRequired()])
    submit            = SubmitField('Créer le compte')


class EtudiantEditionForm(FlaskForm):
    """Édition d'un étudiant existant : pas de changement d'inscription ici."""
    nom    = StringField('Nom', validators=[DataRequired(), Length(max=50)])
    prenom = StringField('Prénom', validators=[DataRequired(), Length(max=50)])
    email  = StringField('Email', validators=[
        DataRequired(), Email(), Length(max=100),
    ])
    submit = SubmitField('Enregistrer')


# ─────────────────────────────────────────────────────────────────────────────
# TYPES DE NOTE
# ─────────────────────────────────────────────────────────────────────────────

class TypeNoteForm(FlaskForm):
    ens_classe_id = SelectField('Enseignement / classe', coerce=int, validators=[DataRequired()])
    libelle       = StringField('Libellé', validators=[
        DataRequired(), Length(min=1, max=80),
    ])
    submit        = SubmitField('Créer')


class TypeNoteEditionForm(FlaskForm):
    libelle = StringField('Libellé', validators=[DataRequired(), Length(max=80)])
    submit  = SubmitField('Enregistrer')


# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS EXCEL
# ─────────────────────────────────────────────────────────────────────────────

class ImportEnseignantsForm(FlaskForm):
    fichier = FileField('Fichier Excel (colonnes : nom, prenom, email)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls', 'csv'], 'Format : .xlsx, .xls ou .csv'),
    ])
    submit  = SubmitField('Importer')


class ImportEtudiantsForm(FlaskForm):
    annee_scolaire_id = SelectField('Année scolaire', coerce=int, validators=[DataRequired()])
    classe_id         = SelectField('Classe', coerce=int, validators=[DataRequired()])
    fichier           = FileField('Fichier Excel (colonnes : nom, prenom, email)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls', 'csv'], 'Format : .xlsx, .xls ou .csv'),
    ])
    submit            = SubmitField('Importer')


class ImportNotesForm(FlaskForm):
    ens_classe_id = SelectField('Enseignement / Classe', coerce=int, validators=[DataRequired()])
    type_note_id  = SelectField('Type de note', coerce=int, validators=[DataRequired()])
    fichier       = FileField('Fichier Excel (colonnes : email, note)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls', 'csv'], 'Format : .xlsx, .xls ou .csv'),
    ])
    submit        = SubmitField('Importer')


# ─────────────────────────────────────────────────────────────────────────────
# COMPTES SECRÉTARIAT
# ─────────────────────────────────────────────────────────────────────────────

class SecretariatForm(FlaskForm):
    nom           = StringField('Nom', validators=[DataRequired(), Length(max=50)])
    prenom        = StringField('Prénom', validators=[DataRequired(), Length(max=50)])
    email         = StringField('Email', validators=[
        DataRequired(), Email(), Length(max=100),
    ])
    mot_de_passe  = PasswordField('Mot de passe', validators=[
        DataRequired(), Length(min=8),
    ])
    confirmation  = PasswordField('Confirmation', validators=[
        DataRequired(),
        EqualTo('mot_de_passe', message='Les mots de passe ne correspondent pas.'),
    ])
    submit        = SubmitField('Créer le compte')


class SecretariatEditionForm(FlaskForm):
    nom    = StringField('Nom', validators=[DataRequired(), Length(max=50)])
    prenom = StringField('Prénom', validators=[DataRequired(), Length(max=50)])
    email  = StringField('Email', validators=[
        DataRequired(), Email(), Length(max=100),
    ])
    submit = SubmitField('Enregistrer')


# ─────────────────────────────────────────────────────────────────────────────
# PROFIL ÉTUDIANT
# ─────────────────────────────────────────────────────────────────────────────

class ProfilEtudiantForm(FlaskForm):
    photo  = FileField('Photo de profil (optionnel)', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Image .jpg ou .png uniquement.'),
    ])
    submit = SubmitField('Enregistrer')


# ─────────────────────────────────────────────────────────────────────────────
# CSRF helper (vide) – utile pour des actions POST sans champ
# ─────────────────────────────────────────────────────────────────────────────

class ActionForm(FlaskForm):
    """Formulaire vide pour les actions POST simples (suppression, etc.).

    Sert uniquement pour la protection CSRF.
    """
    submit = SubmitField('Confirmer')
