# services/user_service.py

import bcrypt
from flask import current_app, flash, redirect, session, url_for

from avatar import generate_avatar_color, is_valid_hex_color, normalize_hex_color, pick_text_color
from utils import execute_query


def ensure_avatar_profile(user_id: int, username: str | None = None) -> str:
    profile = execute_query(
        "SELECT avatar_color FROM user_profile WHERE user_id = :user_id",
        {"user_id": user_id},
        fetchone=True,
    )

    if profile and profile.get("avatar_color") and is_valid_hex_color(profile["avatar_color"]):
        normalized = normalize_hex_color(profile["avatar_color"])
        if profile["avatar_color"] != normalized:
            execute_query(
                "UPDATE user_profile SET avatar_color = :color WHERE user_id = :user_id",
                {"user_id": user_id, "color": normalized},
                commit=True,
            )
        return normalized

    seed = f"{user_id}:{(username or '').lower()}"
    color = normalize_hex_color(generate_avatar_color(seed))
    execute_query(
        """
        INSERT INTO user_profile (user_id, avatar_color)
        VALUES (:user_id, :color)
        ON CONFLICT(user_id) DO UPDATE SET avatar_color = EXCLUDED.avatar_color
        """,
        {"user_id": user_id, "color": color},
        commit=True,
    )
    return color


def build_avatar_context(user_id: int, username: str | None = None) -> dict[str, object]:
    display_name = (username or "").strip()
    color = ensure_avatar_profile(user_id, display_name)
    text_color, needs_border = pick_text_color(color)
    initial = (display_name[:1] or "?").upper()

    return {
        "color": color,
        "text_color": text_color,
        "initial": initial,
        "needs_border": needs_border,
        "title": f"Avatar di {display_name or 'utente'}",
        "aria_label": f"Avatar di {display_name or 'utente'}",
    }

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
    flash("Account eliminato con successo.", "success")
    return redirect(url_for("auth.login"))

def handle_avatar_color_update(user_id: int, raw_color: str | None) -> None:
    if current_app.config.get("AVATAR_MODE", "color") != "color":
        flash("La personalizzazione dell'avatar non è disponibile.", "warning")
        return

    if not raw_color:
        flash("Seleziona un colore per l'avatar.", "danger")
        return

    candidate = raw_color.strip()
    if not is_valid_hex_color(candidate):
        flash("Formato colore non valido. Usa il formato #RRGGBB.", "danger")
        return

    color = normalize_hex_color(candidate)
    execute_query(
        """
        INSERT INTO user_profile (user_id, avatar_color)
        VALUES (:user_id, :color)
        ON CONFLICT(user_id) DO UPDATE SET avatar_color = EXCLUDED.avatar_color
        """,
        {"user_id": user_id, "color": color},
        commit=True,
    )
    flash("Avatar aggiornato con successo.", "success")