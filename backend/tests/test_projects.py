import os
import sqlite3

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from core import database, migrations
from repositories import user_repo
from services import project_service


def test_get_project_returns_owner_project(tmp_path, monkeypatch):
    # 连接入口已统一到 core.database（C8），测试库重定向也改在这里
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "projects.db")
    # 建表统一走迁移（C9）；外键已生效，项目必须挂在真实用户下
    migrations.run_migrations()
    owner_id = user_repo.create_user("owner@test.com", "x")
    other_id = user_repo.create_user("other@test.com", "x")

    created = project_service.create_project(owner_id, "Alpha", "Folder Alpha")

    loaded = project_service.get_project(owner_id, created.id)
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.name == "Alpha"
    assert loaded.project_path == "Folder Alpha"

    assert project_service.get_project(other_id, created.id) is None


def test_migrations_idempotent_and_fk_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "mig.db")
    migrations.run_migrations()
    migrations.run_migrations()  # 幂等：重复执行不报错、版本不乱

    with database.db_connection() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == len(migrations.MIGRATIONS)

    # 外键真的在管事：挂在不存在用户下的项目插不进去
    with pytest.raises(sqlite3.IntegrityError):
        project_service.create_project(99999, "Ghost", "nowhere")


def test_migration_upgrades_legacy_db(tmp_path, monkeypatch):
    """存量库（旧结构 + 孤儿数据）跑迁移：结构补齐、孤儿被清、数据保留。"""
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            profile TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO users (username, password_hash) VALUES ('u@test.com', 'x');
        INSERT INTO messages (user_id, role, content) VALUES (1, 'user', 'hello');
        INSERT INTO messages (user_id, role, content) VALUES (999, 'user', 'orphan');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, "DB_FILE", db_file)
    migrations.run_migrations()

    with database.db_connection() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        assert {"project_id", "attachments_json"} <= cols  # 旧库补列成功
        rows = conn.execute("SELECT user_id, content FROM messages").fetchall()
        assert rows == [(1, "hello")]  # 孤儿消息被清、正常数据保留
