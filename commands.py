# commands.py

import subprocess
import sys

import bcrypt
import click
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError

from bootstrap import ensure_database_indexes
from extensions import db
from migrations import run_migrations
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


@click.command(name='db-upgrade')
@with_appcontext
def db_upgrade_command():
    """Esegue le migrazioni del database."""

    run_migrations()
    click.echo('Migrazioni applicate con successo.')


@click.command(name='db-prepare')
@with_appcontext
def db_prepare_command():
    """Aggiorna lo schema e crea gli indici essenziali."""

    run_migrations()
    ensure_database_indexes()
    click.echo('Database pronto con schema e indici aggiornati.')


@click.command(name='security-scan')
@with_appcontext
def security_scan_command():
    """Esegue le verifiche di sicurezza statiche con Bandit."""

    paths = [
        'app.py',
        'commands.py',
        'extensions.py',
        'routes',
        'services',
        'security.py',
        'utils.py',
    ]
    command = ['bandit', '-q', '-r', *paths]
    click.echo('Esecuzione di Bandit per le verifiche di sicurezza...')

    try:
        result = subprocess.run(command, check=False)
    except FileNotFoundError:
        click.echo(
            "Bandit non è installato nell'ambiente corrente. "
            "Installa le dipendenze (pip install -r requirements.txt) e riprova.",
            err=True,
        )
        sys.exit(1)

    if result.returncode == 0:
        click.echo('Verifiche di sicurezza completate senza vulnerabilità note.')
    else:
        click.echo(
            "Bandit ha rilevato potenziali problemi di sicurezza. "
            "Consulta l'output sopra per i dettagli.",
            err=True,
        )
        sys.exit(result.returncode)


def init_app(app):
    """Registra i comandi CLI con l'applicazione Flask."""
    app.cli.add_command(create_admin_command)
    app.cli.add_command(db_upgrade_command)
    app.cli.add_command(db_prepare_command)
    app.cli.add_command(security_scan_command)

