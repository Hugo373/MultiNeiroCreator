import sqlite3
from datetime import UTC, datetime

from core.config import DB_FILE

# 工程文件一律由前端通过 File System Access API 写入用户本地磁盘，
# 后端只维护"项目名 + id"这张花名册，用于最近项目列表和聊天记录按项目隔离。
# project_path 字段仅保存本地文件夹名作展示标签，后端不做任何文件操作。


def init_projects_table() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            project_path TEXT NOT NULL,
            save_mode TEXT DEFAULT 'manual',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_opened_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def list_recent_projects(user_id: int, limit: int = 8) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
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
    conn.close()

    return [_row_to_project_payload(row) for row in rows]


def get_project(user_id: int, project_id: int) -> dict | None:
    init_projects_table()

    conn = sqlite3.connect(DB_FILE)
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
    conn.close()

    if row is None:
        return None

    return _row_to_project_payload(row)


def create_project(user_id: int, name: str | None = None, project_path: str | None = None) -> dict:
    init_projects_table()

    # 项目名和时间戳按本地时间展示给用户；先取带时区的 UTC 再转本地，避免 naive datetime（DTZ005）
    now = datetime.now(UTC).astimezone()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    project_name = _normalize_project_name(name, now)
    path_label = (project_path or "").strip()[:200] or "本地项目文件夹"

    conn = sqlite3.connect(DB_FILE)
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
    conn.commit()
    project_id = cursor.lastrowid
    conn.close()

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
