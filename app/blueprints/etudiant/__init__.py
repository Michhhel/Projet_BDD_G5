from functools import wraps
from flask import Blueprint, abort
from flask_login import current_user, login_required

etudiant_bp = Blueprint(
    'etudiant', __name__,
    template_folder='../../templates/etudiant',
)


def etudiant_required(f):
    """Décorateur : restreint l'accès aux utilisateurs de type étudiant."""
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not (current_user.is_authenticated and current_user.role == 'etudiant'):
            abort(403)
        return f(*args, **kwargs)
    return wrapper


from app.blueprints.etudiant import routes  # noqa: E402, F401
