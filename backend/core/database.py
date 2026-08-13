import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from core.config import DB_FILE


def get_connection() -> sqlite3.Connection:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=5.0)  # 拿不到写锁时最多等 5 秒再抛 locked
    conn.execute("PRAGMA journal_mode=WAL")  # 读写不再互阻（写与写仍互斥），设置持久化在库文件上
    conn.execute("PRAGMA synchronous=NORMAL")  # WAL 推荐搭档：掉电最多丢最近几次提交，不损库
    conn.execute("PRAGMA foreign_keys=ON")  # SQLite 默认关，每连接都要显式打开
    return conn


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    """数据库连接的唯一推荐入口：正常自动 commit，异常自动 rollback，无论如何必 close。

    注意：sqlite3 的 `with conn` 只管事务不管 close，缺外层 finally 就是连接泄漏。
    """
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    conn = get_connection()
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
    if "project_id" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN project_id INTEGER")
    if "attachments_json" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN attachments_json TEXT")
    # 索引支撑高频查询 WHERE user_id=? [AND project_id=?]（最左前缀覆盖单查 user_id）
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_user_project ON messages(user_id, project_id)"
    )
    conn.commit()
    conn.close()
