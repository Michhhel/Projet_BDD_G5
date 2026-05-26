# =============================================================================
# models.py – Modèle de données ENSEA (Application de suivi des notes)
# Base : PostgreSQL | ORM : Flask-SQLAlchemy | 12 tables
# =============================================================================

from datetime import datetime, timedelta, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint, Index
import re

db = SQLAlchemy()


# =============================================================================
# CONSTANTES & UTILITAIRES MÉTIER
# =============================================================================

# Regex de validation du mot de passe étudiant
_MDP_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[-._@+*]).{8,}$'
)

def valider_mot_de_passe(mdp: str) -> bool:
    """Valide qu'un mot de passe respecte les règles métier :
    - 8 caractères minimum
    - Au moins une majuscule
    - Au moins une minuscule
    - Au moins un chiffre
    - Au moins un caractère spécial parmi : - . _ @ + *
    """
    return bool(_MDP_PATTERN.match(mdp))


DUREE_EXPIRATION_CODE_H = 24  # Durée de validité des codes de réinitialisation


# =============================================================================
# TABLE 1 : SECRETARIAT
# Comptes du personnel de secrétariat (accès complet à l'application)
# =============================================================================

class Secretariat(UserMixin, db.Model):
    __tablename__ = 'secretariat'

    id            = db.Column(db.Integer, primary_key=True)
    nom           = db.Column(db.String(50), nullable=False)
    prenom        = db.Column(db.String(50), nullable=False)
    email         = db.Column(db.String(100), unique=True, nullable=False)
    mot_de_passe  = db.Column(db.String(255), nullable=False)   # stocké hashé (bcrypt)

    # ── Relations (cascade='all, delete-orphan' intentionnellement absent :
    #    les données restent si un secrétaire est supprimé) ──────────────────
    etudiants_crees       = db.relationship('Etudiant',       foreign_keys='Etudiant.cree_par_id',
                                             backref='createur', lazy='dynamic')
    enseignants_enregistres = db.relationship('Enseignant',   foreign_keys='Enseignant.enregistre_par_id',
                                               backref='enregistreur', lazy='dynamic')
    inscriptions_creees   = db.relationship('Inscription',    foreign_keys='Inscription.cree_par_id',
                                             backref='createur', lazy='dynamic')
    enseignements_configures = db.relationship('Enseignement', foreign_keys='Enseignement.configure_par_id',
                                                backref='configurateur', lazy='dynamic')
    types_note_charges    = db.relationship('TypeNote',        foreign_keys='TypeNote.charge_par_id',
                                             backref='chargeur', lazy='dynamic')

    def __repr__(self):
        return f'<Secretariat {self.prenom} {self.nom} ({self.email})>'

    # Flask-Login : distingue secrétariat vs étudiant
    @property
    def role(self):
        return 'secretariat'

    def get_id(self):
        """Format de l'ID pour Flask-Login : 'secretariat:<id>'."""
        return f'secretariat:{self.id}'

    @property
    def nom_complet(self):
        return f'{self.prenom} {self.nom.upper()}'


# =============================================================================
# TABLE 2 : ETUDIANT
# Comptes étudiants – mot de passe unique globalement (contrainte sur le hash)
# =============================================================================

class Etudiant(UserMixin, db.Model):
    __tablename__ = 'etudiant'

    id                = db.Column(db.Integer, primary_key=True)
    nom               = db.Column(db.String(50), nullable=False)
    prenom            = db.Column(db.String(50), nullable=False)
    email             = db.Column(db.String(100), unique=True, nullable=False)
    mot_de_passe_hash = db.Column(db.String(255), unique=True, nullable=False)
    cree_par_id       = db.Column(db.Integer, db.ForeignKey('secretariat.id'), nullable=True)
    photo             = db.Column(db.String(255), nullable=True)  # chemin photo de profil

    # ── Relations ──────────────────────────────────────────────────────────
    inscriptions  = db.relationship('Inscription',   backref='etudiant', lazy='dynamic',
                                     cascade='all, delete-orphan')
    notes         = db.relationship('NoteEtudiant',  backref='etudiant', lazy='dynamic',
                                     cascade='all, delete-orphan')
    codes_reinit  = db.relationship('CodeReinit',    backref='etudiant', lazy='dynamic',
                                     cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Etudiant {self.prenom} {self.nom} ({self.email})>'

    @property
    def nom_complet(self):
        """Renvoie « NOM Prénom » tel qu'affiché dans les menus."""
        return f'{self.nom.upper()} {self.prenom}'

    @property
    def role(self):
        return 'etudiant'

    def get_id(self):
        """Format de l'ID pour Flask-Login : 'etudiant:<id>'."""
        return f'etudiant:{self.id}'


# =============================================================================
# TABLE 3 : ENSEIGNANT
# Référentiel des enseignants – pas de compte, pas de connexion
# =============================================================================

class Enseignant(db.Model):
    __tablename__ = 'enseignant'

    id                  = db.Column(db.Integer, primary_key=True)
    nom                 = db.Column(db.String(50), nullable=False)
    prenom              = db.Column(db.String(50), nullable=False)
    email               = db.Column(db.String(100), unique=True, nullable=False)
    enregistre_par_id   = db.Column(db.Integer, db.ForeignKey('secretariat.id'), nullable=True)

    # ── Relations ──────────────────────────────────────────────────────────
    enseignements = db.relationship('Enseignement', backref='enseignant', lazy='dynamic')

    def __repr__(self):
        return f'<Enseignant {self.prenom} {self.nom}>'

    @property
    def nom_complet(self):
        return f'{self.nom.upper()} {self.prenom}'


# =============================================================================
# TABLE 4 : CLASSE
# Ex. : "ISE1", "AS1_1", "INFO2"
# =============================================================================

class Classe(db.Model):
    __tablename__ = 'classe'

    id  = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), unique=True, nullable=False)

    # ── Relations ──────────────────────────────────────────────────────────
    inscriptions         = db.relationship('Inscription',        backref='classe', lazy='dynamic')
    enseignement_classes = db.relationship('EnseignementClasse', backref='classe', lazy='dynamic')

    def __repr__(self):
        return f'<Classe {self.nom}>'


# =============================================================================
# TABLE 5 : ANNEE_SCOLAIRE
# Ex. : "2024-2025", "2025-2026"
# =============================================================================

class AnneeScolaire(db.Model):
    __tablename__ = 'annee_scolaire'

    id      = db.Column(db.Integer, primary_key=True)
    libelle = db.Column(db.String(20), unique=True, nullable=False)

    # ── Relations ──────────────────────────────────────────────────────────
    inscriptions  = db.relationship('Inscription',  backref='annee_scolaire', lazy='dynamic')
    enseignements = db.relationship('Enseignement', backref='annee_scolaire', lazy='dynamic')

    def __repr__(self):
        return f'<AnneeScolaire {self.libelle}>'


# =============================================================================
# TABLE 6 : MATIERE
# Ex. : "Statistiques", "Mathématiques", "Informatique"
# =============================================================================

class Matiere(db.Model):
    __tablename__ = 'matiere'

    id  = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)

    # ── Relations ──────────────────────────────────────────────────────────
    enseignements = db.relationship('Enseignement', backref='matiere', lazy='dynamic')

    def __repr__(self):
        return f'<Matiere {self.nom}>'


# =============================================================================
# TABLE 7 : INSCRIPTION
# Lien étudiant ↔ classe ↔ année scolaire
# Contrainte : un étudiant ne peut avoir qu'une inscription par année
# =============================================================================

class Inscription(db.Model):
    __tablename__ = 'inscription'
    __table_args__ = (
        UniqueConstraint('etudiant_id', 'annee_scolaire_id',
                         name='uq_inscription_etudiant_annee'),
    )

    id                  = db.Column(db.Integer, primary_key=True)
    etudiant_id         = db.Column(db.Integer, db.ForeignKey('etudiant.id'),       nullable=False)
    classe_id           = db.Column(db.Integer, db.ForeignKey('classe.id'),          nullable=False)
    annee_scolaire_id   = db.Column(db.Integer, db.ForeignKey('annee_scolaire.id'),  nullable=False)
    cree_par_id         = db.Column(db.Integer, db.ForeignKey('secretariat.id'),     nullable=True)
    date_inscription    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Inscription etudiant={self.etudiant_id} classe={self.classe_id} annee={self.annee_scolaire_id}>'


# =============================================================================
# TABLE 8 : ENSEIGNEMENT
# Lien enseignant ↔ matière ↔ année scolaire
# =============================================================================

class Enseignement(db.Model):
    __tablename__ = 'enseignement'
    __table_args__ = (
        UniqueConstraint('enseignant_id', 'matiere_id', 'annee_scolaire_id',
                         name='uq_enseignement_ens_mat_annee'),
    )

    id                = db.Column(db.Integer, primary_key=True)
    enseignant_id     = db.Column(db.Integer, db.ForeignKey('enseignant.id'),       nullable=False)
    matiere_id        = db.Column(db.Integer, db.ForeignKey('matiere.id'),           nullable=False)
    annee_scolaire_id = db.Column(db.Integer, db.ForeignKey('annee_scolaire.id'),    nullable=False)
    configure_par_id  = db.Column(db.Integer, db.ForeignKey('secretariat.id'),       nullable=False)

    # ── Relations ──────────────────────────────────────────────────────────
    enseignement_classes = db.relationship('EnseignementClasse', backref='enseignement',
                                            lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Enseignement ens={self.enseignant_id} mat={self.matiere_id} annee={self.annee_scolaire_id}>'


# =============================================================================
# TABLE 9 : ENSEIGNEMENT_CLASSE (table de jonction many-to-many)
# =============================================================================

class EnseignementClasse(db.Model):
    __tablename__ = 'enseignement_classe'
    __table_args__ = (
        UniqueConstraint('enseignement_id', 'classe_id',
                         name='uq_ens_classe'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    enseignement_id = db.Column(db.Integer, db.ForeignKey('enseignement.id'), nullable=False)
    classe_id       = db.Column(db.Integer, db.ForeignKey('classe.id'),        nullable=False)

    # ── Relations ──────────────────────────────────────────────────────────
    types_note = db.relationship('TypeNote', backref='enseignement_classe',
                                  lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<EnseignementClasse ens={self.enseignement_id} classe={self.classe_id}>'


# =============================================================================
# TABLE 10 : TYPE_NOTE
# Ex. : "Devoir 1", "Devoir 2", "Examen Final", "TP1"
# =============================================================================

class TypeNote(db.Model):
    __tablename__ = 'type_note'
    __table_args__ = (
        UniqueConstraint('ens_classe_id', 'libelle',
                         name='uq_type_note_ens_classe_libelle'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    ens_classe_id   = db.Column(db.Integer, db.ForeignKey('enseignement_classe.id'), nullable=False)
    libelle         = db.Column(db.String(80), nullable=False)
    date_creation   = db.Column(db.Date,    default=date.today,   nullable=False)
    charge_par_id   = db.Column(db.Integer, db.ForeignKey('secretariat.id'),         nullable=False)

    # ── Relations ──────────────────────────────────────────────────────────
    notes_etudiants = db.relationship('NoteEtudiant', backref='type_note',
                                       lazy='dynamic')

    def __repr__(self):
        return f'<TypeNote {self.libelle} (ens_classe={self.ens_classe_id})>'


# =============================================================================
# TABLE 11 : NOTE_ETUDIANT
# Valeur entre 0 et 20 – une seule note par (type_note, étudiant)
# RÈGLE MÉTIER CRITIQUE : jamais supprimée, seulement remplacée par UPDATE
# =============================================================================

class NoteEtudiant(db.Model):
    __tablename__ = 'note_etudiant'
    __table_args__ = (
        UniqueConstraint('type_note_id', 'etudiant_id',
                         name='uq_note_etudiant_type_etu'),
        CheckConstraint('valeur >= 0 AND valeur <= 20',
                        name='ck_note_valeur_0_20'),
    )

    id           = db.Column(db.Integer, primary_key=True)
    type_note_id = db.Column(db.Integer, db.ForeignKey('type_note.id'), nullable=False)
    etudiant_id  = db.Column(db.Integer, db.ForeignKey('etudiant.id'),  nullable=False)
    valeur       = db.Column(db.Numeric(4, 2), nullable=False)
    date_saisie  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date_modification = db.Column(db.DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<NoteEtudiant etu={self.etudiant_id} type={self.type_note_id} val={self.valeur}>'

    @property
    def valeur_float(self):
        return float(self.valeur) if self.valeur is not None else None

    # ── Garde-fou applicatif contre la suppression ─────────────────────────
    @staticmethod
    def interdire_suppression(mapper, connection, target):
        raise RuntimeError(
            "RÈGLE MÉTIER : La suppression d'une note est interdite. "
            "Utilisez une mise à jour (UPDATE) pour remplacer la valeur."
        )


from sqlalchemy import event
event.listen(NoteEtudiant, 'before_delete', NoteEtudiant.interdire_suppression)


# =============================================================================
# TABLE 12 : CODE_REINIT
# Codes temporaires (6 chiffres) pour la réinitialisation des mots de passe
# =============================================================================

class CodeReinit(db.Model):
    __tablename__ = 'code_reinit'

    id              = db.Column(db.Integer, primary_key=True)
    etudiant_id     = db.Column(db.Integer, db.ForeignKey('etudiant.id'), nullable=False)
    code            = db.Column(db.String(6), nullable=False)
    date_creation   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date_expiration = db.Column(db.DateTime, nullable=False)
    utilise         = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<CodeReinit etu={self.etudiant_id} utilise={self.utilise}>'

    @property
    def est_valide(self) -> bool:
        return (not self.utilise) and (datetime.utcnow() < self.date_expiration)

    @classmethod
    def creer(cls, etudiant_id: int, code: str) -> 'CodeReinit':
        return cls(
            etudiant_id     = etudiant_id,
            code            = code,
            date_expiration = datetime.utcnow() + timedelta(hours=DUREE_EXPIRATION_CODE_H),
        )

    def invalider(self):
        self.utilise = True


# =============================================================================
# INDEX SUPPLÉMENTAIRES
# =============================================================================

Index('ix_etudiant_email', Etudiant.email)
Index('ix_inscription_annee_classe', Inscription.annee_scolaire_id, Inscription.classe_id)
Index('ix_note_type_note_id', NoteEtudiant.type_note_id)
Index('ix_code_reinit_etudiant_utilise', CodeReinit.etudiant_id, CodeReinit.utilise)


def init_db(app):
    """Initialise l'extension db avec l'application Flask."""
    db.init_app(app)
