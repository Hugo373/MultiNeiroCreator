"""projects 表的唯一 SQL 出入口（C6）：service 层只谈业务，不碰 SQL。"""

import sqlite3

from core.database import db_connection

_COLUMNS = "id, name, project_path, save_mode, created_at, updated_at, last_opened_at"


def insert(user_id: int, name: str, project_path: str, save_mode: str, timestamp: str) -> int:
    with db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO projects"
            " (user_id, name, project_path, save_mode, created_at, updated_at, last_opened_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, project_path, save_mode, timestamp, timestamp, timestamp),
        )
        project_id = cursor.lastrowid
    assert project_id is not None  # INSERT 成功后 lastrowid 必有值
    return project_id


def list_recent(user_id: int, limit: int) -> list[sqlite3.Row]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            f"SELECT {_COLUMNS} FROM projects WHERE user_id=?"
            " ORDER BY datetime(last_opened_at) DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def get_by_id(user_id: int, project_id: int) -> sqlite3.Row | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            f"SELECT {_COLUMNS} FROM projects WHERE user_id=? AND id=? LIMIT 1",
            (user_id, project_id),
        ).fetchone()
