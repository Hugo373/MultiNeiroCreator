"""documents 表的 SQLite 访问层。

文档原文件由 storage_path 指向磁盘，SQLite 只保存生命周期和索引元数据。
所有查询都带 user_id，避免把一个用户的知识库暴露给另一个用户。
"""

import sqlite3
from typing import Any

from core.database import db_connection

_DOCUMENT_COLUMNS = """id, user_id, project_id, filename, storage_path, status,
size_bytes, file_hash, chunks_count, error_message, job_id, created_at, updated_at, indexed_at"""


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["error"] = item.pop("error_message")
    return item


def _identity_clause() -> str:
    return "user_id=? AND COALESCE(project_id, -1)=COALESCE(?, -1) AND filename=?"


def create_replacement(
    document_id: str,
    user_id: int,
    project_id: int | None,
    filename: str,
    storage_path: str,
    size_bytes: int,
    file_hash: str,
    created_at: str,
) -> tuple[dict[str, Any], list[str]]:
    """将同名旧文档标记删除，再登记一份新的 queued 文档。"""
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        old_rows = conn.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE {_identity_clause()} AND status != 'deleted'",
            (user_id, project_id, filename),
        ).fetchall()
        old_paths = [row["storage_path"] for row in old_rows]
        conn.execute(
            f"UPDATE documents SET status='deleted', error_message=?, updated_at=? "
            f"WHERE {_identity_clause()} AND status != 'deleted'",
            ("已被新版本替换", created_at, user_id, project_id, filename),
        )
        conn.execute(
            "INSERT INTO documents "
            "(id, user_id, project_id, filename, storage_path, status, size_bytes, file_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?)",
            (
                document_id,
                user_id,
                project_id,
                filename,
                storage_path,
                size_bytes,
                file_hash,
                created_at,
                created_at,
            ),
        )
        row = conn.execute(f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE id=?", (document_id,)).fetchone()
    assert row is not None
    return _row_to_dict(row), old_paths


def set_job_id(document_id: str, job_id: str, updated_at: str) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE documents SET job_id=?, updated_at=? WHERE id=? AND status='queued'",
                (job_id, updated_at, document_id),
            ).rowcount
            == 1
        )


def get(document_id: str, user_id: int | None = None) -> dict[str, Any] | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        if user_id is None:
            row = conn.execute(
                f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE id=?", (document_id,)
            ).fetchone()
        else:
            row = conn.execute(
                f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE id=? AND user_id=?",
                (document_id, user_id),
            ).fetchone()
    return _row_to_dict(row) if row else None


def list_for_user(
    user_id: int,
    project_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        if project_id is None:
            rows = conn.execute(
                f"SELECT {_DOCUMENT_COLUMNS} FROM documents "
                "WHERE user_id=? AND status != 'deleted' ORDER BY datetime(updated_at) DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_DOCUMENT_COLUMNS} FROM documents "
                "WHERE user_id=? AND project_id=? AND status != 'deleted' "
                "ORDER BY datetime(updated_at) DESC LIMIT ?",
                (user_id, project_id, limit),
            ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_active_identity(user_id: int, project_id: int | None, filename: str) -> list[dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE {_identity_clause()} AND status != 'deleted'",
            (user_id, project_id, filename),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def queue_for_retry(document_id: str, updated_at: str) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE documents SET status='queued', error_message=NULL, updated_at=? "
                "WHERE id=? AND status IN ('failed', 'cancelled', 'ready')",
                (updated_at, document_id),
            ).rowcount
            == 1
        )


def mark_processing(document_id: str, updated_at: str) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE documents SET status='processing', error_message=NULL, updated_at=? "
                "WHERE id=? AND status IN ('queued', 'failed', 'ready')",
                (updated_at, document_id),
            ).rowcount
            == 1
        )


def mark_ready(document_id: str, chunks_count: int, updated_at: str, indexed_at: str) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE documents SET status='ready', chunks_count=?, error_message=NULL, "
                "updated_at=?, indexed_at=? WHERE id=? AND status='processing'",
                (chunks_count, updated_at, indexed_at, document_id),
            ).rowcount
            == 1
        )


def mark_failed(document_id: str, error: str, updated_at: str) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE documents SET status='failed', error_message=?, updated_at=? "
                "WHERE id=? AND status != 'deleted'",
                (error[:2000], updated_at, document_id),
            ).rowcount
            == 1
        )


def mark_cancelled(document_id: str, updated_at: str) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE documents SET status='cancelled', error_message=?, updated_at=? "
                "WHERE id=? AND status != 'deleted'",
                ("任务已取消", updated_at, document_id),
            ).rowcount
            == 1
        )


def mark_deleted(document_id: str, updated_at: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM documents WHERE id=? AND status != 'deleted'",
            (document_id,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE documents SET status='deleted', error_message=NULL, updated_at=? WHERE id=?",
            (updated_at, document_id),
        )
    return _row_to_dict(row)


def clear_job_id(document_id: str, updated_at: str) -> None:
    with db_connection() as conn:
        conn.execute("UPDATE documents SET job_id=NULL, updated_at=? WHERE id=?", (updated_at, document_id))
