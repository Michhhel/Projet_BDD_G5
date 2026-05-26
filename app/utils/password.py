# =============================================================================
# app/utils/password.py – Gestion des mots de passe étudiants
# =============================================================================
# Règles métier :
#  - 8 caractères minimum
#  - 1 majuscule, 1 minuscule, 1 chiffre, 1 spécial parmi - . _ @ + *
#  - Unicité globale : aucun étudiant ne peut avoir le même mot de passe qu'un
#    autre. Comme on stocke uniquement des hashes bcrypt (irréversibles), on
#    vérifie l'unicité en passant le nouveau clair à bcrypt.checkpw() contre
#    tous les hashes existants.
# =============================================================================

import secrets
import bcrypt

from app.models import valider_mot_de_passe, Etudiant


CARACTERES_SPECIAUX = '-._@+*'
MINUSCULES = 'abcdefghijklmnopqrstuvwxyz'
MAJUSCULES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
CHIFFRES   = '0123456789'


# ─────────────────────────────────────────────────────────────────────────────
# HASH & VÉRIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def hasher_mot_de_passe(mdp_clair: str) -> str:
    """Renvoie le hash bcrypt d'un mot de passe en clair."""
    return bcrypt.hashpw(mdp_clair.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verifier_mot_de_passe(mdp_clair: str, mdp_hash: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond à un hash bcrypt."""
    if not mdp_clair or not mdp_hash:
        return False
    try:
        return bcrypt.checkpw(mdp_clair.encode('utf-8'), mdp_hash.encode('utf-8'))
    except (ValueError, AttributeError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# UNICITÉ GLOBALE
# ─────────────────────────────────────────────────────────────────────────────

def mot_de_passe_deja_utilise(mdp_clair: str, ignorer_etudiant_id: int = None) -> bool:
    """Renvoie True si un autre étudiant utilise déjà ce mot de passe.

    On itère sur tous les hashes existants. Coûteux à grande échelle mais
    inévitable avec bcrypt (irréversible). Acceptable pour quelques centaines
    d'étudiants.
    """
    query = Etudiant.query.with_entities(Etudiant.id, Etudiant.mot_de_passe_hash)
    if ignorer_etudiant_id is not None:
        query = query.filter(Etudiant.id != ignorer_etudiant_id)

    for _id, h in query.all():
        if verifier_mot_de_passe(mdp_clair, h):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# GÉNÉRATION
# ─────────────────────────────────────────────────────────────────────────────

def _melange(chaine: str) -> str:
    """Mélange aléatoirement les caractères d'une chaîne."""
    lst = list(chaine)
    # Fisher-Yates avec secrets pour cryptographique
    for i in range(len(lst) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        lst[i], lst[j] = lst[j], lst[i]
    return ''.join(lst)


def generer_mot_de_passe(longueur: int = 12) -> str:
    """Génère un mot de passe respectant les règles métier.

    Garanti : au moins 1 minuscule, 1 majuscule, 1 chiffre, 1 spécial.
    """
    if longueur < 8:
        longueur = 8

    # Au moins un de chaque catégorie
    obligatoires = [
        secrets.choice(MINUSCULES),
        secrets.choice(MAJUSCULES),
        secrets.choice(CHIFFRES),
        secrets.choice(CARACTERES_SPECIAUX),
    ]
    # Le reste : pool complet
    pool = MINUSCULES + MAJUSCULES + CHIFFRES + CARACTERES_SPECIAUX
    autres = [secrets.choice(pool) for _ in range(longueur - 4)]

    mdp = _melange(''.join(obligatoires + autres))

    # Assurance ceinture+bretelles : si la regex échoue (improbable), on recommence
    if not valider_mot_de_passe(mdp):
        return generer_mot_de_passe(longueur)
    return mdp


def generer_mot_de_passe_etudiant(mdp_clairs_deja_generes: list = None,
                                   max_essais: int = 50) -> tuple[str, str]:
    """Génère un mot de passe unique pour un nouvel étudiant.

    Renvoie (mot_de_passe_clair, hash_bcrypt).
    Vérifie l'unicité en BDD ET dans la liste fournie (utile pour les imports
    en lot où les hashes ne sont pas encore commités).
    """
    mdp_clairs_deja_generes = mdp_clairs_deja_generes or []

    for _ in range(max_essais):
        candidat = generer_mot_de_passe()
        if candidat in mdp_clairs_deja_generes:
            continue
        if mot_de_passe_deja_utilise(candidat):
            continue
        return candidat, hasher_mot_de_passe(candidat)

    raise RuntimeError(
        f"Impossible de générer un mot de passe unique après {max_essais} essais. "
        f"Augmentez la longueur ou vérifiez la table étudiant."
    )
