# =============================================================================
# app/utils/excel.py – Imports / exports Excel
# =============================================================================

import io
import pandas as pd
from typing import Iterable


# Extensions acceptées
EXTENSIONS_VALIDES = {'.xlsx', '.xls', '.csv'}


def fichier_autorise(nom_fichier: str) -> bool:
    """Vérifie que l'extension du fichier est autorisée."""
    if not nom_fichier or '.' not in nom_fichier:
        return False
    ext = '.' + nom_fichier.rsplit('.', 1)[-1].lower()
    return ext in EXTENSIONS_VALIDES


def lire_fichier(file_storage) -> pd.DataFrame:
    """Lit un fichier Excel ou CSV uploadé en DataFrame pandas.

    Lève une ValueError si le format est invalide.
    """
    if file_storage.filename.lower().endswith('.csv'):
        return pd.read_csv(file_storage, dtype=str, keep_default_na=False)

    try:
        return pd.read_excel(file_storage, dtype=str, keep_default_na=False)
    except Exception as exc:
        raise ValueError(f'Impossible de lire le fichier : {exc}')


def valider_colonnes(df: pd.DataFrame, colonnes_requises: list[str]) -> list[str]:
    """Renvoie la liste des colonnes manquantes (vide = OK)."""
    cols_norm = {c.strip().lower() for c in df.columns}
    return [c for c in colonnes_requises if c.lower() not in cols_norm]


def normaliser_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme les colonnes en minuscules, sans espaces."""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def previsualisation(df: pd.DataFrame, n: int = 5) -> list[dict]:
    """Renvoie les `n` premières lignes du DataFrame sous forme de liste de dicts."""
    return df.head(n).fillna('').to_dict(orient='records')


# ─────────────────────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def dataframe_vers_excel_bytes(df: pd.DataFrame, nom_feuille: str = 'Données') -> bytes:
    """Sérialise un DataFrame en bytes Excel (à renvoyer via send_file)."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=nom_feuille[:31])  # Excel limite à 31 car
    buffer.seek(0)
    return buffer.getvalue()


def plusieurs_dataframes_vers_excel(dfs: dict) -> bytes:
    """Sérialise un dict {nom_feuille: DataFrame} en un seul fichier Excel multi-onglets."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for nom, df in dfs.items():
            df.to_excel(writer, index=False, sheet_name=nom[:31])
    buffer.seek(0)
    return buffer.getvalue()


def queryset_vers_dataframe(queryset, colonnes: list[tuple[str, str]]) -> pd.DataFrame:
    """Convertit un queryset SQLAlchemy en DataFrame.

    `colonnes` : liste de tuples (entête_colonne, attribut_ou_callable).
    Exemple : [('Nom', 'nom'), ('Email', 'email'), ('Classe', lambda e: e.classe.nom)]
    """
    lignes = []
    for obj in queryset:
        ligne = {}
        for entete, accesseur in colonnes:
            if callable(accesseur):
                try:
                    val = accesseur(obj)
                except Exception:
                    val = ''
            else:
                val = getattr(obj, accesseur, '')
            ligne[entete] = val if val is not None else ''
        lignes.append(ligne)
    return pd.DataFrame(lignes)
