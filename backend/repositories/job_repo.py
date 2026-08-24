import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from core.database import db_connection

_JOB_COLUMNS = """id, type, status, user_id, project_id, payload_json, result_json,
error_message, progress, progress_message, attempts, max_attempts, next_run_at,
claimed_by, lease_expires_at, cancel_requested, created_at, started_at, finished_at"""


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    result_json = item.pop("result_json")
    item["result"] = json.loads(result_json) if result_json else None
    item["error"] = item.pop("error_message")
    item["cancel_requested"] = bool(item["cancel_requested"])
    return item


def create(
    job_id: str,
    job_type: str,
    user_id: int,
    project_id: int | None,
    payload: dict[str, Any],
    max_attempts: int,
    created_at: str,
) -> dict[str, Any]:
    with db_connection() as conn:
        conn.execute(
            """INSERT INTO jobs
            (id, type, status, user_id, project_id, payload_json, progress,
             attempts, max_attempts, cancel_requested, created_at)
            VALUES (?, ?, 'queued', ?, ?, ?, 0, 0, ?, 0, ?)""",
            (
                job_id,
                job_type,
                user_id,
                project_id,
                json.dumps(payload, ensure_ascii=False),
                max_attempts,
                created_at,
            ),
        )
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row is not None
    return _row_to_dict(row)


def get_for_user(user_id: int, job_id: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id=? AND user_id=?",
            (job_id, user_id),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_for_user(
    user_id: int,
    project_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        if project_id is None:
            rows = conn.execute(
                f"SELECT {_JOB_COLUMNS} FROM jobs WHERE user_id=? ORDER BY datetime(created_at) DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_JOB_COLUMNS} FROM jobs WHERE user_id=? AND project_id=?"
                " ORDER BY datetime(created_at) DESC LIMIT ?",
                (user_id, project_id, limit),
            ).fetchall()
    return [_row_to_dict(row) for row in rows]


def claim_next(worker_id: str, lease_seconds: int, now: str) -> dict[str, Any] | None:
    lease_expires_at = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        # 领取动作必须和查询在同一个 IMMEDIATE 事务里，避免多个 Worker 抢到同一任务。
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            f"SELECT {_JOB_COLUMNS} FROM jobs "
            "WHERE status='queued' AND cancel_requested=0 "
            "AND (next_run_at IS NULL OR next_run_at<=?) "
            "ORDER BY datetime(created_at) ASC LIMIT 1",
            (now,),
        ).fetchone()
        if row is None:
            return None
        updated = conn.execute(
            "UPDATE jobs SET status='running', attempts=attempts+1, claimed_by=?, "
            "lease_expires_at=?, started_at=COALESCE(started_at, ?), progress_message=? "
            "WHERE id=? AND status='queued' AND cancel_requested=0",
            (worker_id, lease_expires_at, now, "任务开始执行", row["id"]),
        ).rowcount
        if updated != 1:
            return None
        claimed = conn.execute(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id=?", (row["id"],)).fetchone()
    assert claimed is not None
    return _row_to_dict(claimed)


def renew_lease(job_id: str, worker_id: str, lease_seconds: int) -> bool:
    lease_expires_at = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE jobs SET lease_expires_at=? WHERE id=? AND status='running' AND claimed_by=?",
                (lease_expires_at, job_id, worker_id),
            ).rowcount
            == 1
        )


def update_progress(job_id: str, worker_id: str, progress: int, message: str | None) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE jobs SET progress=?, progress_message=? "
                "WHERE id=? AND status='running' AND claimed_by=?",
                (progress, message, job_id, worker_id),
            ).rowcount
            == 1
        )


def mark_succeeded(job_id: str, worker_id: str, result: dict[str, Any], finished_at: str) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE jobs SET status='succeeded', progress=100, progress_message=?, result_json=?, "
                "finished_at=?, lease_expires_at=NULL WHERE id=? AND status='running' AND claimed_by=?",
                ("任务完成", json.dumps(result, ensure_ascii=False), finished_at, job_id, worker_id),
            ).rowcount
            == 1
        )


def mark_cancelled(job_id: str, worker_id: str, finished_at: str) -> bool:
    with db_connection() as conn:
        return (
            conn.execute(
                "UPDATE jobs SET status='cancelled', progress_message=?, finished_at=?, lease_expires_at=NULL "
                "WHERE id=? AND status='running' AND claimed_by=?",
                ("任务已取消", finished_at, job_id, worker_id),
            ).rowcount
            == 1
        )


def mark_failed_or_retry(
    job_id: str,
    worker_id: str,
    error: str,
    retry_at: str | None,
    finished_at: str,
) -> str | None:
    """失败时重新排队；retry_at 为 None 表示已耗尽次数，最终失败。"""
    next_status = "queued" if retry_at else "failed"
    message = "等待重试" if retry_at else "任务失败"
    with db_connection() as conn:
        updated = conn.execute(
            "UPDATE jobs SET status=?, error_message=?, progress_message=?, next_run_at=?, "
            "finished_at=?, lease_expires_at=NULL, claimed_by=NULL "
            "WHERE id=? AND status='running' AND claimed_by=?",
            (
                next_status,
                error[:2000],
                message,
                retry_at,
                None if retry_at else finished_at,
                job_id,
                worker_id,
            ),
        ).rowcount
    return next_status if updated == 1 else None


def retry_failed(user_id: int, job_id: str, now: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        updated = conn.execute(
            "UPDATE jobs SET status='queued', attempts=0, error_message=NULL, result_json=NULL, "
            "progress=0, progress_message='等待人工重试', next_run_at=NULL, cancel_requested=0, "
            "finished_at=NULL, started_at=NULL WHERE id=? AND user_id=? AND status='failed'",
            (job_id, user_id),
        ).rowcount
        if updated != 1:
            return None
        row = conn.execute(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row is not None
    return _row_to_dict(row)


def request_cancel(user_id: int, job_id: str, now: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id=? AND user_id=?", (job_id, user_id)
        ).fetchone()
        if row is None:
            return None
        if row["status"] == "queued":
            conn.execute(
                "UPDATE jobs SET status='cancelled', finished_at=?, progress_message=? WHERE id=?",
                (now, "任务已取消", job_id),
            )
        elif row["status"] == "running":
            conn.execute("UPDATE jobs SET cancel_requested=1 WHERE id=?", (job_id,))
        row = conn.execute(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert row is not None
    return _row_to_dict(row)


def is_cancel_requested(job_id: str, worker_id: str) -> bool:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT cancel_requested FROM jobs WHERE id=? AND status='running' AND claimed_by=?",
            (job_id, worker_id),
        ).fetchone()
    return bool(row and row[0])


def recover_expired(now: str, retry_at: str | None) -> int:
    """恢复过期任务；超过最大尝试次数的任务进入 failed，不能无限重试。"""
    with db_connection() as conn:
        # 先重置仍可重试的文档；耗尽次数的文档转 failed，避免 processing 僵尸。
        conn.execute(
            "UPDATE documents SET status='queued', error_message=?, updated_at=? "
            "WHERE status='processing' AND job_id IN ("
            "SELECT id FROM jobs WHERE status='running' AND lease_expires_at IS NOT NULL "
            "AND lease_expires_at<? AND attempts < max_attempts"
            ")",
            ("Worker 异常退出，等待重新索引", now, now),
        )
        conn.execute(
            "UPDATE documents SET status='failed', error_message=?, updated_at=? "
            "WHERE status='processing' AND job_id IN ("
            "SELECT id FROM jobs WHERE status='running' AND lease_expires_at IS NOT NULL "
            "AND lease_expires_at<? AND attempts >= max_attempts"
            ")",
            ("Worker 异常退出，已达到最大重试次数", now, now),
        )
        conn.execute(
            "UPDATE jobs SET status='failed', error_message=?, finished_at=?, "
            "claimed_by=NULL, lease_expires_at=NULL, progress_message=? "
            "WHERE status='running' AND lease_expires_at IS NOT NULL "
            "AND lease_expires_at<? AND attempts >= max_attempts",
            ("Worker 异常退出，已达到最大重试次数", now, "任务失败", now),
        )
        return conn.execute(
            "UPDATE jobs SET status='queued', claimed_by=NULL, lease_expires_at=NULL, "
            "next_run_at=?, progress_message=? "
            "WHERE status='running' AND lease_expires_at IS NOT NULL "
            "AND lease_expires_at<? AND attempts < max_attempts",
            (retry_at, "Worker 已恢复任务", now),
        ).rowcount
