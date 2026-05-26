# =============================================================================
# run.py – Point d'entrée de l'application ENSEA
# =============================================================================
# Local  : python run.py
# Render : gunicorn run:app
# =============================================================================

import os
from app import create_app
from app.models import db

env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)


@app.shell_context_processor
def make_shell_context():
    """Variables disponibles dans `flask shell`."""
    from app.models import (
        Secretariat, Etudiant, Enseignant, Classe, AnneeScolaire, Matiere,
        Inscription, Enseignement, EnseignementClasse, TypeNote,
        NoteEtudiant, CodeReinit,
    )
    return {
        'db': db,
        'Secretariat': Secretariat, 'Etudiant': Etudiant, 'Enseignant': Enseignant,
        'Classe': Classe, 'AnneeScolaire': AnneeScolaire, 'Matiere': Matiere,
        'Inscription': Inscription, 'Enseignement': Enseignement,
        'EnseignementClasse': EnseignementClasse, 'TypeNote': TypeNote,
        'NoteEtudiant': NoteEtudiant, 'CodeReinit': CodeReinit,
    }


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=app.config['DEBUG'])
