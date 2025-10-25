# services/user_service.py

import bcrypt
import uuid
from pathlib import Path
from flask import current_app, flash, redirect, session, url_for
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps, UnidentifiedImageError

from utils import execute_query, allowed_file

def _upload_directory() -> Path:
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "static/profile_pics")
    path = Path(current_app.root_path) / upload_dir
    path.mkdir(parents=True, exist_ok=True)
    return path

def _delete_profile_image(filename: str):
    if not filename:
        return
    file_path = _upload_directory() / filename
    try:
        if file_path.exists():
            file_path.unlink()
    except OSError as exc:
        current_app.logger.warning("Impossibile eliminare l'immagine del profilo %s: %s", file_path, exc)

def _save_profile_image(file_storage) -> str:
    extension = file_storage.filename.rsplit(".", 1)[1].lower()
    new_filename = secure_filename(f"{uuid.uuid4().hex}.{extension}")
    destination = _upload_directory() / new_filename
    file_storage.stream.seek(0)
    try:
        with Image.open(file_storage.stream) as img:
            processed = ImageOps.exif_transpose(img)
            processed.thumbnail((300, 300))
            processed.save(destination)
        return new_filename
    except (UnidentifiedImageError, OSError) as exc:
        current_app.logger.warning("Caricamento immagine non riuscito: %s", exc)
        raise ValueError("Immagine non valida") from exc

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

    profile_to_delete = execute_query("SELECT profile_image_file FROM user_profile WHERE user_id = :user_id", {"user_id": user_id}, fetchone=True)
    if profile_to_delete and profile_to_delete.get("profile_image_file"):
        _delete_profile_image(profile_to_delete["profile_image_file"])

    execute_query("DELETE FROM users WHERE id = :id", {"id": user_id}, commit=True)
    session.clear()
    flash("Account eliminato con successo.", "success")
    return redirect(url_for("auth.login"))

def handle_picture_upload(user_id, file):
    if not file or file.filename == "" or not allowed_file(file.filename):
        flash("File non valido o non selezionato.", "danger")
        return

    profile = execute_query("SELECT profile_image_file FROM user_profile WHERE user_id = :user_id", {"user_id": user_id}, fetchone=True)
    
    try:
        new_filename = _save_profile_image(file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return

    if profile and profile.get("profile_image_file"):
        _delete_profile_image(profile["profile_image_file"])

    query = "INSERT INTO user_profile (user_id, profile_image_file) VALUES (:user_id, :filename) ON CONFLICT(user_id) DO UPDATE SET profile_image_file = EXCLUDED.profile_image_file"
    execute_query(query, {"user_id": user_id, "filename": new_filename}, commit=True)
    flash("Immagine aggiornata.", "success")

def handle_picture_deletion(user_id):
    profile = execute_query("SELECT profile_image_file FROM user_profile WHERE user_id = :user_id", {"user_id": user_id}, fetchone=True)
    if profile and profile.get("profile_image_file"):
        _delete_profile_image(profile["profile_image_file"])
        execute_query("UPDATE user_profile SET profile_image_file = NULL WHERE user_id = :user_id", {"user_id": user_id}, commit=True)
        flash("Immagine eliminata.", "success")