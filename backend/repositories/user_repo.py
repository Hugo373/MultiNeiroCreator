import sqlite3

from core.database import db_connection


def get_user_by_username(username: str) -> sqlite3.Row | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT id, username, password_hash, profile, created_at FROM users WHERE username=?",
            (username,),
        ).fetchone()


def create_user(username: str, password_hash: str) -> int:
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        user_id = cursor.lastrowid
    assert user_id is not None  # INSERT 成功后 lastrowid 必有值
    return user_id


def get_profile(user_id: int) -> str:
    with db_connection() as conn:
        row = conn.execute("SELECT profile FROM users WHERE id=?", (user_id,)).fetchone()
    return row[0] if row else ""


def update_profile(user_id: int, profile: str) -> None:
    with db_connection() as conn:
        conn.execute("UPDATE users SET profile=? WHERE id=?", (profile, user_id))
