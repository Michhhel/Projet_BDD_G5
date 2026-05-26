# =============================================================================
# app/utils/pdf.py – Génération de PDF (relevés de notes, bulletins)
# =============================================================================

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)


# Couleurs ENSEA (bleu institutionnel)
COULEUR_PRIMAIRE   = colors.HexColor('#003366')
COULEUR_SECONDAIRE = colors.HexColor('#0066CC')
COULEUR_GRIS       = colors.HexColor('#F5F5F5')


def _styles():
    """Renvoie les styles partagés."""
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name='Titre',  parent=base['Heading1'],
        fontSize=18, textColor=COULEUR_PRIMAIRE, alignment=1, spaceAfter=12,
    ))
    base.add(ParagraphStyle(
        name='SousTitre', parent=base['Heading2'],
        fontSize=12, textColor=COULEUR_SECONDAIRE, alignment=1, spaceAfter=8,
    ))
    base.add(ParagraphStyle(
        name='Info', parent=base['Normal'],
        fontSize=10, spaceAfter=4,
    ))
    return base


def _entete(elements, styles, titre: str, sous_titre: str = ''):
    """Ajoute l'en-tête institutionnel ENSEA."""
    elements.append(Paragraph('ÉCOLE NATIONALE SUPÉRIEURE DE STATISTIQUE', styles['Titre']))
    elements.append(Paragraph('ET D\'ÉCONOMIE APPLIQUÉE — ENSEA Abidjan', styles['SousTitre']))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(titre, styles['Titre']))
    if sous_titre:
        elements.append(Paragraph(sous_titre, styles['SousTitre']))
    elements.append(Spacer(1, 0.5 * cm))


def _pied(elements, styles):
    """Ajoute le pied de page."""
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(
        f'<i>Document généré le {datetime.now().strftime("%d/%m/%Y à %Hh%M")}</i>',
        styles['Info'],
    ))


# ─────────────────────────────────────────────────────────────────────────────
# RELEVÉ DE NOTES INDIVIDUEL (côté étudiant)
# ─────────────────────────────────────────────────────────────────────────────

def releve_notes_etudiant(etudiant, annee_libelle: str, donnees: list[dict]) -> bytes:
    """Génère le PDF du relevé de notes d'un étudiant.

    `donnees` : liste de dicts par matière, contenant au moins :
       { 'matiere': str, 'moyenne': float|None, 'mention': str,
         'rang': int|None, 'effectif': int,
         'notes': [{'libelle': str, 'note': float, 'moyenne_classe': float}, ...] }
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )
    styles = _styles()
    elements = []

    _entete(elements, styles,
            'Relevé de notes individuel',
            f'Année scolaire {annee_libelle}')

    # Bloc identité
    bloc_identite = [
        ['Nom complet :', etudiant.nom_complet],
        ['Email :',       etudiant.email],
        ['Année :',       annee_libelle],
    ]
    t = Table(bloc_identite, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), COULEUR_PRIMAIRE),
        ('BACKGROUND', (0, 0), (-1, -1), COULEUR_GRIS),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.8 * cm))

    # Tableau récapitulatif par matière
    en_tetes = ['Matière', 'Moyenne', 'Mention', 'Rang', 'Effectif']
    rows = [en_tetes]
    for mat in donnees:
        rows.append([
            mat['matiere'],
            f"{mat['moyenne']:.2f}" if mat.get('moyenne') is not None else '—',
            mat.get('mention', '—'),
            f"{mat['rang']}/{mat['effectif']}" if mat.get('rang') else '—',
            str(mat.get('effectif', 0)),
        ])

    t = Table(rows, colWidths=[6*cm, 2.5*cm, 3*cm, 2*cm, 2*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COULEUR_PRIMAIRE),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 10),
        ('ALIGN',      (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN',      (0, 0), (0, -1),  'LEFT'),
        ('GRID',       (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COULEUR_GRIS]),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)

    # Détail par matière (notes individuelles)
    for mat in donnees:
        if not mat.get('notes'):
            continue
        elements.append(Spacer(1, 0.6 * cm))
        elements.append(Paragraph(f"<b>Détail — {mat['matiere']}</b>", styles['SousTitre']))
        sous_rows = [['Évaluation', 'Note obtenue', 'Moyenne classe']]
        for n in mat['notes']:
            sous_rows.append([
                n['libelle'],
                f"{n['note']:.2f}" if n['note'] is not None else '—',
                f"{n['moyenne_classe']:.2f}" if n.get('moyenne_classe') is not None else '—',
            ])
        st = Table(sous_rows, colWidths=[8*cm, 4*cm, 4*cm])
        st.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COULEUR_SECONDAIRE),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 9),
            ('ALIGN',      (1, 0), (-1, -1), 'CENTER'),
            ('GRID',       (0, 0), (-1, -1), 0.3, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COULEUR_GRIS]),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(st)

    _pied(elements, styles)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# BULLETIN DE CLASSE (côté secrétariat)
# ─────────────────────────────────────────────────────────────────────────────

def bulletin_classe(titre: str, sous_titre: str, en_tetes: list[str],
                     lignes: list[list], stats: dict | None = None) -> bytes:
    """Génère un PDF tabulaire pour un bulletin/classement de classe.

    `lignes` : chaque sous-liste est une ligne (déjà formatée en str).
    `stats`  : optionnel, dict {label: valeur} pour bloc statistiques en bas.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )
    styles = _styles()
    elements = []

    _entete(elements, styles, titre, sous_titre)

    rows = [en_tetes] + lignes
    n_cols = len(en_tetes)
    # Largeur de colonne égale
    col_width = (A4[0] - 3*cm) / n_cols
    t = Table(rows, colWidths=[col_width] * n_cols, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COULEUR_PRIMAIRE),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COULEUR_GRIS]),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)

    # Bloc statistiques
    if stats:
        elements.append(Spacer(1, 0.8 * cm))
        elements.append(Paragraph('<b>Statistiques descriptives</b>', styles['SousTitre']))
        srows = [[k, str(v)] for k, v in stats.items()]
        st = Table(srows, colWidths=[6*cm, 4*cm])
        st.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), COULEUR_PRIMAIRE),
            ('BACKGROUND', (0, 0), (-1, -1), COULEUR_GRIS),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(st)

    _pied(elements, styles)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
