import sqlite3

from core.config import DB_FILE


def get_connection() -> sqlite3.Connection:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    # timeout=5：拿不到写锁时最多等 5 秒再抛 database is locked。
    # Python 的 sqlite3 默认就是 5.0，但显式写出来：这是声明过的配置，不是碰运气的默认值（C7）
    conn = sqlite3.connect(DB_FILE, timeout=5.0)
    # WAL：写追加到 .wal 日志文件，读写不再互相阻塞（写与写仍互斥）。
    # 该设置持久化在数据库文件上，重复执行是廉价 no-op
    conn.execute("PRAGMA journal_mode=WAL")
    # WAL 的推荐搭档：fsync 频率从"每次提交"降为"checkpoint 时"，写入更快；
    # 掉电最多丢最近几次提交，不会损坏数据库本身，对聊天记录场景是合理权衡
    conn.execute("PRAGMA synchronous=NORMAL")
    # 外键约束默认是关的（SQLite 历史包袱），每个连接都要显式打开；
    # 当前表还没声明 FOREIGN KEY（补声明需重建表，归 C9 迁移），先把开关打开保证声明后即刻生效
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
    # 复合索引支撑高频查询 WHERE user_id=? AND project_id=?（C7）；
    # 按最左前缀原则，单查 user_id 也能命中
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_user_project ON messages(user_id, project_id)"
    )
    conn.commit()
    conn.close()
