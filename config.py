# =============================================================================
# config.py – Configuration de l'application ENSEA
# =============================================================================

import os
from datetime import timedelta
from dotenv import load_dotenv

# Charge .env si présent
load_dotenv()

BASEDIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Configuration de base partagée par tous les environnements."""

    # Sécurité
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-NE-PAS-UTILISER-EN-PROD'

    # Base de données
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or 'postgresql://postgres:postgres@localhost:5432/ensea_notes'
    )
    # Render fournit parfois "postgres://" qu'il faut remplacer par "postgresql://"
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }

    # Sessions
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=7)

    # Uploads
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    UPLOAD_FOLDER = os.path.join(BASEDIR, 'uploads')
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get(
        'MAIL_DEFAULT_SENDER', 'ENSEA Notes <noreply@ensea.ci>'
    )
    # Si pas de credentials, on tombe en mode "console" : les mots de passe
    # générés s'affichent dans le terminal au lieu d'être envoyés par email.
    MAIL_SUPPRESS_SEND = not bool(MAIL_USERNAME and MAIL_PASSWORD)

    # Pagination
    ITEMS_PER_PAGE = 25


class DevelopmentConfig(Config):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class ProductionConfig(Config):
    DEBUG = False
    # En prod, forcer une vraie SECRET_KEY
    @classmethod
    def init_app(cls, app):
        assert cls.SECRET_KEY and cls.SECRET_KEY != 'dev-secret-key-NE-PAS-UTILISER-EN-PROD', \
            "SECRET_KEY doit être définie en production"


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
