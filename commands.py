# commands.py

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError
import bcrypt

from extensions import db
from migrations import run_migrations
from utils import execute_query
from services.user_service import ensure_avatar_profile

@click.command(name='create-admin')
@with_appcontext
def create_admin_command():
    """Crea un utente amministratore interattivamente."""
    
    username = click.prompt('Inserisci il nome utente per l-amministratore', type=str)
    password = click.prompt('Inserisci la password', hide_input=True, confirmation_prompt=True)
    
    if not username or not password:
        click.echo('Errore: Nome utente e password non possono essere vuoti.')
        return

    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    try:
        query = """
            INSERT INTO users (username, password, is_admin, has_seen_welcome_message)
            VALUES (:username, :password, 1, 1)
            RETURNING id
        """
        params = {'username': username, 'password': hashed_pw}
        result = execute_query(query, params, fetchone=True, commit=True)

        if result and result.get('id'):
            ensure_avatar_profile(result['id'], username)

        click.echo(f"Utente amministratore '{username}' creato con successo.")
    
    except IntegrityError:
        db.session.rollback()
        click.echo(f"Errore: L'utente '{username}' esiste già.")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Si è verificato un errore imprevisto: {e}")


@click.command(name='db-upgrade')
@with_appcontext
def db_upgrade_command():
    """Esegue le migrazioni del database."""

    run_migrations()
    click.echo('Migrazioni applicate con successo.')


def init_app(app):
    """Registra i comandi CLI con l'applicazione Flask."""
    app.cli.add_command(create_admin_command)
    app.cli.add_command(db_upgrade_command)