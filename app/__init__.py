# =============================================================================
# app/__init__.py – Factory de l'application Flask ENSEA
# =============================================================================

import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_mail import Mail

from config import config
from app.models import db, Secretariat, Etudiant


# Extensions globales (init dans la factory)
login_manager = LoginManager()
migrate       = Migrate()
mail          = Mail()


def create_app(config_name='default'):
    """Crée et configure une instance Flask."""
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config[config_name])

    # Création du dossier uploads si nécessaire
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── Initialisation des extensions ────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    login_manager.init_app(app)
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'warning'

    # Charge l'utilisateur depuis l'ID en session
    # Format de l'ID : "secretariat:42" ou "etudiant:17"
    @login_manager.user_loader
    def load_user(user_id):
        try:
            role, uid = user_id.split(':')
            uid = int(uid)
        except (ValueError, AttributeError):
            return None
        if role == 'secretariat':
            return Secretariat.query.get(uid)
        if role == 'etudiant':
            return Etudiant.query.get(uid)
        return None

    # Redirection contextuelle selon le rôle quand login requis
    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect(url_for('auth.choisir_role'))

    # ── Enregistrement des blueprints ────────────────────────────────────
    from app.blueprints.auth        import auth_bp
    from app.blueprints.secretariat import secretariat_bp
    from app.blueprints.etudiant    import etudiant_bp

    app.register_blueprint(auth_bp,        url_prefix='/auth')
    app.register_blueprint(secretariat_bp, url_prefix='/secretariat')
    app.register_blueprint(etudiant_bp,    url_prefix='/etudiant')

    # ── Route racine : redirige selon l'utilisateur connecté ─────────────
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.role == 'secretariat':
                return redirect(url_for('secretariat.dashboard'))
            return redirect(url_for('etudiant.espace'))
        return redirect(url_for('auth.choisir_role'))

    # ── Filtres et globals Jinja ─────────────────────────────────────────
    @app.template_filter('format_note')
    def format_note(val):
        """Formate une note (Decimal/float) en chaîne ##.## ou '—'."""
        if val is None:
            return '—'
        try:
            return f'{float(val):.2f}'
        except (TypeError, ValueError):
            return '—'

    @app.template_filter('mention')
    def mention_filter(val):
        """Retourne la mention correspondant à une moyenne."""
        if val is None:
            return ''
        v = float(val)
        if v >= 16: return 'Très Bien'
        if v >= 14: return 'Bien'
        if v >= 12: return 'Assez Bien'
        if v >= 10: return 'Passable'
        return 'Insuffisant'

    @app.template_filter('mention_class')
    def mention_class(val):
        """Classe CSS Bootstrap selon la mention."""
        if val is None:
            return 'secondary'
        v = float(val)
        if v >= 16: return 'success'
        if v >= 14: return 'primary'
        if v >= 12: return 'info'
        if v >= 10: return 'warning'
        return 'danger'

    # ── Handlers d'erreur ────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    return app
