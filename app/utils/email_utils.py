# =============================================================================
# app/utils/email_utils.py – Envoi d'emails (avec fallback console)
# =============================================================================

import socket
from flask import current_app, render_template_string
from flask_mail import Message


# Templates d'email (inline pour rester simple)

TEMPLATE_NOUVEAU_COMPTE = """\
Bonjour {{ prenom }} {{ nom }},

Votre compte étudiant ENSEA vient d'être créé.

Voici vos identifiants de connexion :
  • Email        : {{ email }}
  • Mot de passe : {{ mot_de_passe }}

Vous pouvez vous connecter sur : {{ url }}

⚠ Pour des raisons de sécurité, nous vous recommandons de changer votre mot de
  passe après votre première connexion.

Cordialement,
Le secrétariat de l'ENSEA
"""

TEMPLATE_RESET_PASSWORD = """\
Bonjour {{ prenom }} {{ nom }},

Une demande de réinitialisation de mot de passe a été effectuée pour votre
compte étudiant.

Votre code de vérification (valable {{ duree_h }} heures) :

        ╔══════════╗
        ║  {{ code }}  ║
        ╚══════════╝

Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.

Cordialement,
Le secrétariat de l'ENSEA
"""

TEMPLATE_NOUVEAU_MOT_DE_PASSE = """\
Bonjour {{ prenom }} {{ nom }},

Votre mot de passe a été réinitialisé par le secrétariat.

Voici votre nouveau mot de passe :
  {{ mot_de_passe }}

Nous vous recommandons de le changer après votre prochaine connexion.

Cordialement,
Le secrétariat de l'ENSEA
"""

TEMPLATE_CHANGEMENT_CONFIRME = """\
Bonjour {{ prenom }} {{ nom }},

Votre mot de passe a été modifié avec succès le {{ date }}.

Si vous n'êtes pas à l'origine de ce changement, contactez immédiatement le
secrétariat de l'ENSEA.

Cordialement,
Le secrétariat de l'ENSEA
"""


def _envoyer(sujet: str, destinataires: list[str], corps: str) -> bool:
    """Envoie un email ou, en l'absence de configuration SMTP, l'affiche en console.

    IMPORTANT : en production, re-lève l'exception en cas d'échec SMTP
    pour que les routes puissent afficher un message flash au lieu d'un 500.
    """
    # ── Mode développement : MAIL_SUPPRESS_SEND=True ou MAIL_USERNAME absent ──
    # On affiche dans la console sans toucher au SMTP.
    suppress = current_app.config.get('MAIL_SUPPRESS_SEND', False)
    username = current_app.config.get('MAIL_USERNAME', '')

    if suppress or not username:
        print('\n' + '=' * 70)
        print(f'[EMAIL SIMULÉ] Sujet : {sujet}')
        print(f'À : {", ".join(destinataires)}')
        print('-' * 70)
        print(corps)
        print('=' * 70 + '\n')
        return True

    # ── Mode production : envoi SMTP réel avec timeout de 10 secondes ────────
    # Sans timeout, une connexion SMTP qui traîne bloque la requête Flask
    # jusqu'à ce que Render la tue → Internal Server Error.
    socket.setdefaulttimeout(10)

    try:
        from app import mail
        msg = Message(
            subject=sujet,
            recipients=destinataires,
            body=corps,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
        )
        mail.send(msg)
        current_app.logger.info(f'Email envoyé à {", ".join(destinataires)} : {sujet}')
        return True

    except Exception as exc:
        # On logue ET on re-lève : le routes.py attrape l'exception
        # et affiche un flash warning au lieu de planter avec un 500.
        current_app.logger.error(
            f'Échec envoi email à {", ".join(destinataires)} '
            f'({type(exc).__name__}) : {exc}'
        )
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions publiques – signatures inchangées
# ─────────────────────────────────────────────────────────────────────────────

def envoyer_nouveau_compte(etudiant, mot_de_passe_clair: str, url_connexion: str) -> bool:
    """Envoie les identifiants à un nouvel étudiant."""
    corps = render_template_string(
        TEMPLATE_NOUVEAU_COMPTE,
        prenom=etudiant.prenom, nom=etudiant.nom,
        email=etudiant.email,
        mot_de_passe=mot_de_passe_clair,
        url=url_connexion,
    )
    return _envoyer(
        sujet='[ENSEA] Création de votre compte étudiant',
        destinataires=[etudiant.email],
        corps=corps,
    )


def envoyer_code_reset(etudiant, code: str, duree_h: int = 24) -> bool:
    """Envoie un code de réinitialisation."""
    corps = render_template_string(
        TEMPLATE_RESET_PASSWORD,
        prenom=etudiant.prenom, nom=etudiant.nom,
        code=code, duree_h=duree_h,
    )
    return _envoyer(
        sujet='[ENSEA] Réinitialisation de votre mot de passe',
        destinataires=[etudiant.email],
        corps=corps,
    )


def envoyer_nouveau_mot_de_passe(etudiant, mot_de_passe_clair: str) -> bool:
    """Envoie un nouveau mot de passe (reset par secrétariat)."""
    corps = render_template_string(
        TEMPLATE_NOUVEAU_MOT_DE_PASSE,
        prenom=etudiant.prenom, nom=etudiant.nom,
        mot_de_passe=mot_de_passe_clair,
    )
    return _envoyer(
        sujet='[ENSEA] Votre mot de passe a été réinitialisé',
        destinataires=[etudiant.email],
        corps=corps,
    )


def envoyer_confirmation_changement(etudiant, date_str: str) -> bool:
    """Confirme à l'étudiant qu'il a bien changé son mot de passe."""
    corps = render_template_string(
        TEMPLATE_CHANGEMENT_CONFIRME,
        prenom=etudiant.prenom, nom=etudiant.nom,
        date=date_str,
    )
    return _envoyer(
        sujet='[ENSEA] Confirmation du changement de mot de passe',
        destinataires=[etudiant.email],
        corps=corps,
    )