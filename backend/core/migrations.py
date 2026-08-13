"""轻量顺序迁移机制（C9）：全部 DDL 的唯一住所。

- 版本号存 `PRAGMA user_version`（写在库文件头部，随事务提交/回滚），
  启动时把 [当前版本+1, 最新] 的迁移按序执行，每个迁移一个事务；
- 改表结构 = 追加一条新迁移，**永远不改历史迁移**（存量库只认序号）；
- SQLite 不支持 ALTER TABLE ADD FOREIGN KEY，补外键只能按官方十二步法重建表
  （见 _m002）：建新表 → 搬数据 → 删旧表 → 改名 → 重建索引。
"""

import logging
import sqlite3
from collections.abc import Callable

from core import database

logger = logging.getLogger("migrations")

Migration = tuple[str, Callable[[sqlite3.Connection], None]]


def _m001_baseline(conn: sqlite3.Connection) -> None:
    """基线：与存量库结构完全一致（users / messages / projects + 索引）。

    IF NOT EXISTS + 补列写法兼容两种起点：全新库从零建齐；
    存量库（user_version=0 但表已在）跑一遍等于 no-op。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            profile TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            project_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            attachments_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # 早期版本的 messages 没有这两列，存量库在此补齐
    columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
    if "project_id" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN project_id INTEGER")
    if "attachments_json" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN attachments_json TEXT")
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
    # 索引支撑高频查询 WHERE user_id=? [AND project_id=?]（最左前缀覆盖单查 user_id）
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_user_project ON messages(user_id, project_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id)")


def _m002_add_foreign_keys(conn: sqlite3.Connection) -> None:
    """重建 messages / projects，补上基线欠下的 FOREIGN KEY 声明。

    先清孤儿数据（否则启用外键后 foreign_key_check 报错）：
    归属已不存在用户的行直接删；指向已不存在项目的消息回落到默认会话。
    """
    # 重跑安全：Python sqlite3 的 DDL 在隐式事务外执行，上次中途失败可能残留 _new 表
    conn.execute("DROP TABLE IF EXISTS projects_new")
    conn.execute("DROP TABLE IF EXISTS messages_new")
    conn.execute("DELETE FROM projects WHERE user_id NOT IN (SELECT id FROM users)")
    conn.execute("DELETE FROM messages WHERE user_id NOT IN (SELECT id FROM users)")
    conn.execute(
        "UPDATE messages SET project_id=NULL"
        " WHERE project_id IS NOT NULL AND project_id NOT IN (SELECT id FROM projects)"
    )

    conn.execute(
        """
        CREATE TABLE projects_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            project_path TEXT NOT NULL,
            save_mode TEXT DEFAULT 'manual',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_opened_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO projects_new SELECT id, user_id, name, project_path, save_mode,"
        " created_at, updated_at, last_opened_at FROM projects"
    )
    conn.execute("DROP TABLE projects")
    conn.execute("ALTER TABLE projects_new RENAME TO projects")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id)")

    conn.execute(
        """
        CREATE TABLE messages_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            attachments_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "INSERT INTO messages_new SELECT id, user_id, project_id, role, content,"
        " attachments_json, created_at FROM messages"
    )
    conn.execute("DROP TABLE messages")
    conn.execute("ALTER TABLE messages_new RENAME TO messages")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_user_project ON messages(user_id, project_id)"
    )


MIGRATIONS: list[Migration] = [
    ("baseline: users/messages/projects + indexes", _m001_baseline),
    ("add foreign keys via table rebuild", _m002_add_foreign_keys),
]


def run_migrations() -> None:
    """把数据库推进到最新版本。幂等：已是最新则什么都不做。"""
    conn = database.get_connection()
    try:
        # 重建表期间必须关外键（否则 DROP TABLE 被引用检查拦住）；
        # PRAGMA foreign_keys 在事务内是 no-op，所以要在开事务前执行
        conn.execute("PRAGMA foreign_keys=OFF")
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        latest = len(MIGRATIONS)
        if current > latest:
            raise RuntimeError(
                f"数据库版本 {current} 超过代码已知最新版本 {latest}，"
                "可能在跑旧代码，拒绝启动以免损坏数据"
            )
        for number in range(current + 1, latest + 1):
            name, apply = MIGRATIONS[number - 1]
            with conn:  # 一个迁移一个事务：中途失败整体回滚，user_version 不前进
                apply(conn)
                conn.execute(f"PRAGMA user_version={number}")
            logger.info(
                "迁移完成", extra={"evt": "migration_applied", "version": number, "migration": name}
            )
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"迁移后外键校验失败：{violations[:5]}")
    finally:
        conn.close()
