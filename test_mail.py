"""
test_mail.py – Script de diagnostic email
Lance-le sur Render via la console Shell :
  python test_mail.py

Il te dira exactement pourquoi les emails ne partent pas.
"""
import os, sys, socket
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("DIAGNOSTIC EMAIL")
print("=" * 60)

# 1. Vérification des variables d'environnement
print("\n1. Variables d'environnement :")
vars_requises = ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USERNAME',
                 'MAIL_PASSWORD', 'MAIL_USE_TLS']
manquantes = []
for v in vars_requises:
    val = os.environ.get(v, '')
    if val:
        affichage = val[:4] + '***' if 'PASSWORD' in v else val
        print(f"   ✅ {v} = {affichage}")
    else:
        print(f"   ❌ {v} = NON DÉFINIE")
        manquantes.append(v)

if manquantes:
    print(f"\n❌ Variables manquantes : {manquantes}")
    sys.exit(1)

# 2. Test de connectivité réseau vers smtp.gmail.com:587
print("\n2. Connectivité réseau vers smtp.gmail.com:587 :")
try:
    socket.setdefaulttimeout(8)
    sock = socket.create_connection(('smtp.gmail.com', 587), timeout=8)
    sock.close()
    print("   ✅ Port 587 accessible")
except Exception as e:
    print(f"   ❌ Port 587 BLOQUÉ : {e}")
    print("   → Render bloque ce port. Solution : utiliser Resend ou SendGrid.")
    sys.exit(1)

# 3. Test de connectivité vers smtp.gmail.com:465 (SSL)
print("\n3. Connectivité réseau vers smtp.gmail.com:465 (SSL) :")
try:
    sock = socket.create_connection(('smtp.gmail.com', 465), timeout=8)
    sock.close()
    print("   ✅ Port 465 accessible")
except Exception as e:
    print(f"   ❌ Port 465 aussi bloqué : {e}")

# 4. Test SMTP réel
print("\n4. Test d'authentification SMTP :")
import smtplib
server_name = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
port        = int(os.environ.get('MAIL_PORT', 587))
username    = os.environ.get('MAIL_USERNAME', '')
password    = os.environ.get('MAIL_PASSWORD', '')

try:
    with smtplib.SMTP(server_name, port, timeout=8) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(username, password)
        print(f"   ✅ Authentification réussie pour {username}")

    # 5. Envoi d'un vrai email de test
    print(f"\n5. Envoi d'un email de test à {username} :")
    with smtplib.SMTP(server_name, port, timeout=8) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(username, password)
        smtp.sendmail(
            from_addr=username,
            to_addrs=[username],
            msg=f"Subject: [ENSEA] Test email\n\nTest email depuis Render. Ca fonctionne !"
        )
    print(f"   ✅ Email envoyé ! Vérifie ta boîte {username}")

except smtplib.SMTPAuthenticationError as e:
    print(f"   ❌ Authentification échouée : {e}")
    print("   → Le MAIL_PASSWORD n'est pas un mot de passe d'application Gmail.")
    print("   → Génère-en un sur : myaccount.google.com → Sécurité → Mots de passe des applications")
except socket.timeout:
    print("   ❌ Timeout : connexion trop lente ou bloquée par Render/Gmail")
    print("   → Solution recommandée : utiliser Resend (voir ci-dessous)")
except Exception as e:
    print(f"   ❌ Erreur : {type(e).__name__} : {e}")

print("\n" + "=" * 60)
print("FIN DU DIAGNOSTIC")
print("=" * 60)