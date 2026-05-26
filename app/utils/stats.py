# =============================================================================
# app/utils/stats.py – Statistiques descriptives
# =============================================================================

import statistics
from collections import Counter
from typing import Iterable


def _to_floats(valeurs: Iterable) -> list[float]:
    """Convertit en liste de floats en ignorant None."""
    out = []
    for v in valeurs:
        if v is None:
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def stats_descriptives(valeurs: Iterable) -> dict:
    """Calcule les statistiques descriptives complètes.

    Renvoie un dict avec : effectif, moyenne, mediane, mode, min, max,
    Q1, Q3, ecart_type. Renvoie des None si effectif insuffisant.
    """
    notes = _to_floats(valeurs)
    n = len(notes)

    if n == 0:
        return {
            'effectif':   0,
            'moyenne':    None,
            'mediane':    None,
            'mode':       None,
            'min':        None,
            'max':        None,
            'q1':         None,
            'q3':         None,
            'ecart_type': None,
        }

    notes_triees = sorted(notes)
    moyenne = statistics.fmean(notes)
    mediane = statistics.median(notes_triees)

    # Mode : valeur la plus fréquente (arrondie à 0.5 pour éviter le bruit)
    compteur = Counter(round(x * 2) / 2 for x in notes)
    mode_valeur, mode_freq = compteur.most_common(1)[0]
    mode = mode_valeur if mode_freq > 1 else None

    ecart_type = statistics.stdev(notes) if n >= 2 else 0.0

    # Quartiles : méthode "inclusive" (compatible Python 3.8+)
    if n >= 4:
        q = statistics.quantiles(notes_triees, n=4, method='inclusive')
        q1, q3 = q[0], q[2]
    elif n >= 2:
        q1 = notes_triees[0]
        q3 = notes_triees[-1]
    else:
        q1 = q3 = notes_triees[0]

    return {
        'effectif':   n,
        'moyenne':    round(moyenne, 2),
        'mediane':    round(mediane, 2),
        'mode':       round(mode, 2) if mode is not None else None,
        'min':        round(min(notes), 2),
        'max':        round(max(notes), 2),
        'q1':         round(q1, 2),
        'q3':         round(q3, 2),
        'ecart_type': round(ecart_type, 2),
    }


def calculer_rangs(notes_par_etudiant: dict) -> dict:
    """À partir d'un dict {etudiant_id: note_moyenne}, renvoie {etudiant_id: rang}.

    Méthode "dense ranking" : deux ex-aequo partagent le même rang, le suivant
    décale d'autant. Ex : 18, 15, 15, 12 → rangs 1, 2, 2, 3.
    """
    if not notes_par_etudiant:
        return {}

    # Tri décroissant par note
    couples = sorted(notes_par_etudiant.items(), key=lambda kv: -float(kv[1]))

    rangs = {}
    rang = 0
    derniere_note = None
    for etu_id, note in couples:
        if note != derniere_note:
            rang += 1
            derniere_note = note
        rangs[etu_id] = rang
    return rangs


def histogramme_bins(valeurs: Iterable, nb_bins: int = 10) -> tuple[list, list]:
    """Répartit les notes en intervalles de largeur fixe entre 0 et 20.

    Renvoie (labels, comptes) prêts pour Chart.js.
    """
    notes = _to_floats(valeurs)
    largeur = 20.0 / nb_bins
    bins = [0] * nb_bins
    for n in notes:
        idx = min(int(n / largeur), nb_bins - 1)
        bins[idx] += 1

    labels = [
        f'{i * largeur:.0f}-{(i + 1) * largeur:.0f}'
        for i in range(nb_bins)
    ]
    return labels, bins


def repartition_mentions(valeurs: Iterable) -> dict:
    """Compte les notes par tranche de mention.

    Renvoie {'Très Bien': N, 'Bien': N, ...} prêt pour un pie chart.
    """
    notes = _to_floats(valeurs)
    counts = {
        'Très Bien':   0,
        'Bien':        0,
        'Assez Bien':  0,
        'Passable':    0,
        'Insuffisant': 0,
    }
    for n in notes:
        if   n >= 16: counts['Très Bien']   += 1
        elif n >= 14: counts['Bien']        += 1
        elif n >= 12: counts['Assez Bien']  += 1
        elif n >= 10: counts['Passable']    += 1
        else:         counts['Insuffisant'] += 1
    return counts


def moyenne_simple(valeurs: Iterable) -> float | None:
    """Moyenne arithmétique – None si vide."""
    notes = _to_floats(valeurs)
    return round(statistics.fmean(notes), 2) if notes else None
