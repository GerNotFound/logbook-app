# services/user_service.py

import bcrypt
from flask import flash, redirect, session, url_for

from utils import execute_query

def handle_password_change(user_id, current_password_str, new_password_str):
    user = execute_query("SELECT * FROM users WHERE id = :id", {"id": user_id}, fetchone=True)
    if not user:
        flash("Utente non trovato.", "danger")
        return
    
    current_password = current_password_str.encode('utf-8')
    new_password = new_password_str.encode('utf-8')

    if not bcrypt.checkpw(current_password, user["password"].encode("utf-8")):
        flash("Password attuale non corretta.", "danger")
        return

    hashed_pw = bcrypt.hashpw(new_password, bcrypt.gensalt()).decode("utf-8")
    execute_query(
        "UPDATE users SET password = :password WHERE id = :id",
        {"password": hashed_pw, "id": user_id},
        commit=True,
    )
    flash("Password aggiornata con successo.", "success")

def handle_account_deletion(user_id, password_confirm_str):
    if session.get("is_admin"):
        flash("Gli amministratori non possono eliminare il proprio account.", "danger")
        return redirect(url_for("main.impostazioni"))

    user = execute_query("SELECT * FROM users WHERE id = :id", {"id": user_id}, fetchone=True)
    if not user:
        flash("Utente non trovato.", "danger")
        return redirect(url_for("main.impostazioni"))
        
    password_confirm = password_confirm_str.encode('utf-8')
    if not bcrypt.checkpw(password_confirm, user["password"].encode("utf-8")):
        flash("Password non corretta.", "danger")
        return redirect(url_for("main.impostazioni"))

    execute_query("DELETE FROM users WHERE id = :id", {"id": user_id}, commit=True)
    session.clear()
    session.modified = True
    flash("Account eliminato con successo.", "success")
    return redirect(url_for("auth.login"))