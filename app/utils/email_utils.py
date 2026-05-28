# =============================================================================
# app/utils/email_utils.py – Version Resend (remplace Flask-Mail)
# Resend est gratuit jusqu'à 3 000 emails/mois, fonctionne sur tous les clouds
# Doc : https://resend.com/docs/send-with-python
# =============================================================================

import socket
import os
from flask import current_app, render_template_string

# Templates (inchangés par rapport à la version précédente)

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

Votre code de vérification (valable {{ duree_h }} heures) :

        ╔══════════╗
        ║  {{ code }}  ║
        ╚══════════╝

Cordialement,
Le secrétariat de l'ENSEA
"""

TEMPLATE_NOUVEAU_MOT_DE_PASSE = """\
Bonjour {{ prenom }} {{ nom }},

Votre mot de passe a été réinitialisé par le secrétariat.

Nouveau mot de passe : {{ mot_de_passe }}

Cordialement,
Le secrétariat de l'ENSEA
"""

TEMPLATE_CHANGEMENT_CONFIRME = """\
Bonjour {{ prenom }} {{ nom }},

Votre mot de passe a été modifié avec succès le {{ date }}.

Cordialement,
Le secrétariat de l'ENSEA
"""


def _envoyer(sujet: str, destinataires: list, corps: str) -> bool:
    """
    Envoie un email via :
      - Resend  si RESEND_API_KEY est définie  (production recommandée)
      - SMTP    si MAIL_USERNAME est défini     (fallback Gmail)
      - Console si rien n'est configuré         (développement)
    """

    # ── Mode console (développement) ─────────────────────────────────────────
    resend_key = current_app.config.get('RESEND_API_KEY', '')
    mail_user  = current_app.config.get('MAIL_USERNAME', '')

    if not resend_key and not mail_user:
        print('\n' + '=' * 70)
        print(f'[EMAIL SIMULÉ] Sujet : {sujet}')
        print(f'À : {", ".join(destinataires)}')
        print('-' * 70)
        print(corps)
        print('=' * 70 + '\n')
        return True

    # ── Mode Resend (production recommandée) ──────────────────────────────────
    if resend_key:
        try:
            import resend
            resend.api_key = resend_key
            expediteur = current_app.config.get(
                'MAIL_DEFAULT_SENDER', 'noreply@ensea.ci'
            )
            resend.Emails.send({
                "from":    expediteur,
                "to":      destinataires,
                "subject": sujet,
                "text":    corps,
            })
            current_app.logger.info(
                f"[Resend] Email envoyé à {', '.join(destinataires)}"
            )
            return True
        except Exception as exc:
            current_app.logger.error(f"[Resend] Échec : {exc}")
            raise

    # ── Mode SMTP Gmail (fallback) ────────────────────────────────────────────
    socket.setdefaulttimeout(10)
    try:
        from app import mail
        from flask_mail import Message
        msg = Message(
            subject=sujet,
            recipients=destinataires,
            body=corps,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
        )
        mail.send(msg)
        current_app.logger.info(
            f"[SMTP] Email envoyé à {', '.join(destinataires)}"
        )
        return True
    except Exception as exc:
        current_app.logger.error(f"[SMTP] Échec : {type(exc).__name__} – {exc}")
        raise


# ── Fonctions publiques (signatures identiques à l'original) ─────────────────

def envoyer_nouveau_compte(etudiant, mot_de_passe_clair: str,
                            url_connexion: str) -> bool:
    corps = render_template_string(
        TEMPLATE_NOUVEAU_COMPTE,
        prenom=etudiant.prenom, nom=etudiant.nom,
        email=etudiant.email,
        mot_de_passe=mot_de_passe_clair,
        url=url_connexion,
    )
    return _envoyer('[ENSEA] Création de votre compte étudiant',
                    [etudiant.email], corps)


def envoyer_code_reset(etudiant, code: str, duree_h: int = 24) -> bool:
    corps = render_template_string(
        TEMPLATE_RESET_PASSWORD,
        prenom=etudiant.prenom, nom=etudiant.nom,
        code=code, duree_h=duree_h,
    )
    return _envoyer('[ENSEA] Réinitialisation de votre mot de passe',
                    [etudiant.email], corps)


def envoyer_nouveau_mot_de_passe(etudiant, mot_de_passe_clair: str) -> bool:
    corps = render_template_string(
        TEMPLATE_NOUVEAU_MOT_DE_PASSE,
        prenom=etudiant.prenom, nom=etudiant.nom,
        mot_de_passe=mot_de_passe_clair,
    )
    return _envoyer('[ENSEA] Votre mot de passe a été réinitialisé',
                    [etudiant.email], corps)


def envoyer_confirmation_changement(etudiant, date_str: str) -> bool:
    corps = render_template_string(
        TEMPLATE_CHANGEMENT_CONFIRME,
        prenom=etudiant.prenom, nom=etudiant.nom,
        date=date_str,
    )
    return _envoyer('[ENSEA] Confirmation du changement de mot de passe',
                    [etudiant.email], corps)