# =============================================================================
# test_mail.py – Diagnostic de l'envoi d'email (à exécuter en standalone)
# =============================================================================
# Usage : python test_mail.py
#
# Ce script lit les variables MAIL_* de votre .env puis tente d'envoyer un
# email à VOUS-MÊME (MAIL_USERNAME). Cela permet d'isoler les problèmes
# de credentials Gmail sans passer par toute l'app Flask.
# =============================================================================

import os
import smtplib
import ssl
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

MAIL_SERVER          = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT            = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS         = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
MAIL_USERNAME        = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD        = os.environ.get('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER  = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)

print('=' * 70)
print('DIAGNOSTIC EMAIL ENSEA')
print('=' * 70)
print(f'Serveur SMTP   : {MAIL_SERVER}:{MAIL_PORT}')
print(f'TLS activé     : {MAIL_USE_TLS}')
print(f'Username       : {MAIL_USERNAME}')
print(f'Password long. : {len(MAIL_PASSWORD) if MAIL_PASSWORD else 0} caractères')
print(f'Password aper. : {MAIL_PASSWORD[:4] + "..." + MAIL_PASSWORD[-2:] if MAIL_PASSWORD else "(vide)"}')
print(f'Sender         : {MAIL_DEFAULT_SENDER}')
print('=' * 70)

if not MAIL_USERNAME or not MAIL_PASSWORD:
    print('[ERREUR] MAIL_USERNAME ou MAIL_PASSWORD vide dans .env')
    raise SystemExit(1)

# Pour Gmail : le mot de passe d'application doit faire EXACTEMENT 16 caractères
# (sans espaces). Si la longueur est différente, c'est probablement un mauvais
# copier-coller.
if MAIL_SERVER == 'smtp.gmail.com' and len(MAIL_PASSWORD) != 16:
    print(f'[!] ATTENTION : un mot de passe Gmail d\'application fait 16 caractères '
          f'(le vôtre en fait {len(MAIL_PASSWORD)}). Vérifiez le copier-coller.')

# Construction du message
msg = MIMEText('Ceci est un test d\'envoi depuis ENSEA Notes. Si vous recevez ce '
               'mail, votre configuration SMTP fonctionne correctement.')
msg['Subject'] = '[ENSEA] Test SMTP'
msg['From']    = MAIL_DEFAULT_SENDER
msg['To']      = MAIL_USERNAME    # On s'envoie à soi-même

print('\n[..] Connexion au serveur SMTP ...')
try:
    if MAIL_USE_TLS:
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=30)
        server.set_debuglevel(1)         # ← affiche tout le dialogue SMTP
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
    else:
        server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, timeout=30)
        server.set_debuglevel(1)

    print('\n[..] Authentification ...')
    server.login(MAIL_USERNAME, MAIL_PASSWORD)
    print('[OK] Authentification réussie !')

    print('\n[..] Envoi du message ...')
    server.sendmail(MAIL_USERNAME, [MAIL_USERNAME], msg.as_string())
    print('[OK] Email envoyé avec succès à', MAIL_USERNAME)

    server.quit()
    print('\n=== TEST RÉUSSI ===')
    print('Allez vérifier votre boîte mail (et le dossier SPAM).')

except smtplib.SMTPAuthenticationError as exc:
    print(f'\n[ERREUR AUTH] {exc.smtp_code} : {exc.smtp_error.decode()}')
    print('\nCAUSES POSSIBLES :')
    print('  1. Validation en 2 étapes pas activée sur le compte Google')
    print('     → https://myaccount.google.com/security')
    print('  2. Mot de passe d\'application invalide / révoqué')
    print('     → https://myaccount.google.com/apppasswords')
    print('     → Générer un NOUVEAU mot de passe et remplacer dans .env')
    print('  3. MAIL_USERNAME ne correspond pas au compte qui a généré le App Password')
    print('  4. Compte Google Workspace : l\'admin a peut-être bloqué les App Passwords')

except smtplib.SMTPException as exc:
    print(f'\n[ERREUR SMTP] {exc}')

except Exception as exc:
    print(f'\n[ERREUR INATTENDUE] {type(exc).__name__} : {exc}')
