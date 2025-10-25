"""Introduce avatar_color for user profiles."""

from __future__ import annotations

from sqlalchemy import text

from avatar import generate_avatar_color, is_valid_hex_color, normalize_hex_color
from extensions import db

revision = "0002_add_avatar_color"


def upgrade() -> None:
    db.session.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'user_profile' AND column_name = 'avatar_color'
                ) THEN
                    ALTER TABLE user_profile ADD COLUMN avatar_color TEXT;
                END IF;
            END $$;
            """
        )
    )
    db.session.commit()

    rows = db.session.execute(
        text(
            """
            SELECT u.id, u.username, up.avatar_color
            FROM users u
            LEFT JOIN user_profile up ON up.user_id = u.id
            ORDER BY u.id
            """
        )
    ).mappings()

    for row in rows:
        existing = row.get("avatar_color")
        if existing and is_valid_hex_color(existing):
            continue
        seed = f"{row['id']}:{row['username'] or ''}"
        color = normalize_hex_color(generate_avatar_color(seed))
        db.session.execute(
            text(
                """
                INSERT INTO user_profile (user_id, avatar_color)
                VALUES (:user_id, :color)
                ON CONFLICT (user_id)
                DO UPDATE SET avatar_color = EXCLUDED.avatar_color
                """
            ),
            {"user_id": row["id"], "color": color},
        )
    db.session.commit()

    null_rows = db.session.execute(
        text(
            """
            SELECT u.id, u.username
            FROM users u
            JOIN user_profile up ON up.user_id = u.id
            WHERE up.avatar_color IS NULL OR up.avatar_color = ''
            """
        )
    ).mappings()

    for row in null_rows:
        seed = f"{row['id']}:{row['username'] or ''}"
        color = normalize_hex_color(generate_avatar_color(seed))
        db.session.execute(
            text(
                """
                UPDATE user_profile
                SET avatar_color = :color
                WHERE user_id = :user_id
                """
            ),
            {"user_id": row["id"], "color": color},
        )
    db.session.commit()

    db.session.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'user_profile' AND column_name = 'avatar_color'
                ) THEN
                    RETURN;
                END IF;

                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'user_profile_avatar_color_format'
                      AND conrelid = 'user_profile'::regclass
                ) THEN
                    ALTER TABLE user_profile
                        ADD CONSTRAINT user_profile_avatar_color_format
                        CHECK (avatar_color ~ '^#[0-9A-Fa-f]{6}$');
                END IF;
            END $$;
            """
        )
    )

    db.session.execute(
        text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'user_profile'
                      AND column_name = 'avatar_color'
                ) THEN
                    ALTER TABLE user_profile
                        ALTER COLUMN avatar_color SET NOT NULL;
                END IF;
            END $$;
            """
        )
    )
    db.session.commit()
