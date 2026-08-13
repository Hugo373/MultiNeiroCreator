import sqlite3
from datetime import UTC, datetime

from core.database import db_connection

# 工程文件由前端写入用户本地磁盘，后端只维护项目花名册；
# project_path 仅作展示标签，后端不做任何文件操作。
# 建表/索引统一由 core/migrations.py 在启动时完成（C9）。


def list_recent_projects(user_id: int, limit: int = 8) -> list[dict]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
        """
        SELECT id, name, project_path, save_mode, created_at, updated_at, last_opened_at
        FROM projects
        WHERE user_id=?
        ORDER BY datetime(last_opened_at) DESC, id DESC
        LIMIT ?
        """,
            (user_id, limit),
        ).fetchall()

    return [_row_to_project_payload(row) for row in rows]


def get_project(user_id: int, project_id: int) -> dict | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
        """
        SELECT id, name, project_path, save_mode, created_at, updated_at, last_opened_at
        FROM projects
        WHERE user_id=? AND id=?
        LIMIT 1
        """,
            (user_id, project_id),
        ).fetchone()

    if row is None:
        return None

    return _row_to_project_payload(row)


def create_project(user_id: int, name: str | None = None, project_path: str | None = None) -> dict:
    # 先取带时区的 UTC 再转本地，避免 naive datetime
    now = datetime.now(UTC).astimezone()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    project_name = _normalize_project_name(name, now)
    path_label = (project_path or "").strip()[:200] or "本地项目文件夹"

    with db_connection() as conn:
        cursor = conn.execute(
            """
        INSERT INTO projects (user_id, name, project_path, save_mode, created_at, updated_at, last_opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                project_name,
                path_label,
                "manual",
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        project_id = cursor.lastrowid

    return {
        "id": project_id,
        "name": project_name,
        "project_path": path_label,
        "save_mode": "manual",
        "created_at": timestamp,
        "updated_at": timestamp,
        "last_opened_at": timestamp,
    }


def _row_to_project_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "project_path": row["project_path"],
        "save_mode": row["save_mode"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_opened_at": row["last_opened_at"],
    }


def _normalize_project_name(name: str | None, now: datetime) -> str:
    cleaned = (name or "").strip()
    if cleaned:
        return cleaned[:120]
    return f"未命名项目 {now.strftime('%Y%m%d-%H%M%S')}"
