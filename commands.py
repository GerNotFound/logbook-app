# commands.py

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError
import bcrypt

from extensions import db
from utils import execute_query

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
        """
        params = {'username': username, 'password': hashed_pw}
        execute_query(query, params, commit=True)
        
        click.echo(f"Utente amministratore '{username}' creato con successo.")
    
    except IntegrityError:
        db.session.rollback()
        click.echo(f"Errore: L'utente '{username}' esiste già.")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Si è verificato un errore imprevisto: {e}")

def init_app(app):
    """Registra i comandi CLI con l'applicazione Flask."""
    app.cli.add_command(create_admin_command)