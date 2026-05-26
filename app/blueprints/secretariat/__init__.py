from functools import wraps
from flask import Blueprint, abort
from flask_login import current_user, login_required

secretariat_bp = Blueprint(
    'secretariat', __name__,
    template_folder='../../templates/secretariat',
)


def secretariat_required(f):
    """Décorateur : restreint l'accès aux utilisateurs de type secretariat."""
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not (current_user.is_authenticated and current_user.role == 'secretariat'):
            abort(403)
        return f(*args, **kwargs)
    return wrapper


from app.blueprints.secretariat import routes  # noqa: E402, F401
