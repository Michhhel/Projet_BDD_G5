# =============================================================================
# app/utils/annee.py – Validation des libellés d'années scolaires
# =============================================================================

import re
from datetime import date

_ANNEE_PATTERN = re.compile(r'^(\d{4})-(\d{4})$')


def valider_libelle_annee(libelle: str) -> tuple[bool, str]:
    """Valide un libellé d'année scolaire.

    Règles :
      - Format YYYY-YYYY
      - annee2 = annee1 + 1
      - annee1 ne peut pas être supérieure à l'année courante + 1
      - annee1 raisonnable (>= 2000)

    Renvoie (ok, message_erreur).
    """
    if not libelle:
        return False, "Le libellé est obligatoire."

    libelle = libelle.strip()
    match = _ANNEE_PATTERN.match(libelle)
    if not match:
        return False, "Format attendu : YYYY-YYYY (ex. 2024-2025)."

    a1, a2 = int(match.group(1)), int(match.group(2))

    if a2 != a1 + 1:
        return False, f"La seconde année doit valoir {a1 + 1} (et non {a2})."

    if a1 < 2000:
        return False, "L'année de début doit être ≥ 2000."

    annee_courante = date.today().year
    if a1 > annee_courante + 1:
        return False, (
            f"L'année de début ({a1}) ne peut pas être postérieure à "
            f"{annee_courante + 1} (= année courante + 1)."
        )

    return True, ''
