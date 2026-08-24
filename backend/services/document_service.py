"""E3 文档生命周期：原文件落盘，索引工作交给持久化 Worker。"""

import asyncio
import hashlib
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from fastapi import HTTPException, UploadFile

from core import config
from repositories import document_repo, job_repo, project_repo
from services.job_service import create_job
from services.rag.service import add_document, delete_document

ALLOWED_CONTENT_TYPES = {
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".json": {"application/json", "text/plain"},
    ".csv": {"text/csv", "text/plain"},
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def display_filename(raw_filename: str | None) -> str:
    """只保留展示名；存储路径永远使用随机 document_id，不信任客户端路径。"""
    name = (raw_filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=422, detail="上传文件必须有合法文件名")
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="仅支持 TXT、MD、JSON、CSV、PDF、DOCX 文件")
    return name


def _storage_path(document_id: str, user_id: int, project_id: int | None, filename: str) -> Path:
    # 目录层级只来自服务端数字 ID；suffix 仅用于让排查磁盘文件更直观。
    suffix = Path(filename).suffix.lower()
    scope = str(project_id) if project_id is not None else "default"
    return config.DOCUMENT_STORAGE_DIR / str(user_id) / scope / f"{document_id}{suffix}"


def _copy_upload(source: BinaryIO, target: Path) -> tuple[int, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    source.seek(0)
    hasher = hashlib.sha256()
    total = 0
    with target.open("wb") as destination:
        while chunk := source.read(1024 * 1024):
            destination.write(chunk)
            hasher.update(chunk)
            total += len(chunk)
    return total, hasher.hexdigest()


def _remove_file(path: str) -> None:
    # 数据库状态是主账本；清理失败不能让已经接受的上传变成 500。
    with suppress(OSError):
        Path(path).unlink(missing_ok=True)


async def enqueue_upload(
    file: UploadFile,
    user_id: int,
    project_id: int | None,
    size_bytes: int,
) -> dict[str, Any]:
    filename = display_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    content_type = file.content_type or ""
    if (
        content_type
        and content_type != "application/octet-stream"
        and content_type not in ALLOWED_CONTENT_TYPES[suffix]
    ):
        raise HTTPException(status_code=415, detail="文件扩展名与 MIME 类型不匹配")
    if project_id is not None and project_repo.get_by_id(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    document_id = uuid.uuid4().hex
    target = _storage_path(document_id, user_id, project_id, filename)
    actual_size, file_hash = await asyncio.to_thread(_copy_upload, file.file, target)
    if actual_size > size_bytes:
        await asyncio.to_thread(_remove_file, str(target))
        raise HTTPException(status_code=413, detail="上传文件大小校验失败")

    created_at = utc_now()
    try:
        document, old_paths = document_repo.create_replacement(
            document_id=document_id,
            user_id=user_id,
            project_id=project_id,
            filename=filename,
            storage_path=str(target),
            size_bytes=actual_size,
            file_hash=file_hash,
            created_at=created_at,
        )
        for old_path in old_paths:
            await asyncio.to_thread(_remove_file, old_path)
        # 替换先清理旧版本的派生向量；旧 Worker 即使稍后写回，也会因 document_id
        # 不同而被自己的收尾清理，不会误删新版本。
        await asyncio.to_thread(
            delete_document,
            filename,
            user_id,
            project_id,
        )

        job = create_job(
            user_id=user_id,
            job_type="document_ingest",
            payload={"document_id": document_id},
            project_id=project_id,
        )
        if not document_repo.set_job_id(document_id, job["id"], utc_now()):
            raise RuntimeError("文档已被替换，无法绑定索引任务")
        document = document_repo.get(document_id, user_id)
        assert document is not None
        return {
            "status": "accepted",
            "message": f"已接收文档：{filename}，正在后台建立索引",
            "document": document,
            "job": job,
        }
    except Exception:
        document_repo.mark_failed(document_id, "任务创建失败", utc_now())
        await asyncio.to_thread(_remove_file, str(target))
        raise


def process_document(
    document_id: str,
    update_progress: Any,
    is_cancel_requested: Any,
) -> dict[str, Any]:
    """Worker 内执行：原文件 -> 解析 -> chunk -> 批量 embedding -> Chroma。"""
    document = document_repo.get(document_id)
    if document is None:
        raise ValueError("文档不存在")
    if document["status"] == "deleted":
        raise InterruptedError("文档已删除")
    if document["status"] == "cancelled":
        raise InterruptedError("文档任务已取消")
    if is_cancel_requested():
        document_repo.mark_cancelled(document_id, utc_now())
        raise InterruptedError("文档索引任务已取消")
    if not document_repo.mark_processing(document_id, utc_now()):
        raise ValueError(f"文档当前状态不可处理：{document['status']}")

    try:
        update_progress(10, "正在解析原始文档")
        path = Path(document["storage_path"])
        if not path.is_file():
            raise FileNotFoundError("原始文档文件不存在，无法建立索引")
        chunks_count = add_document(
            file_path=str(path),
            filename=document["filename"],
            user_id=document["user_id"],
            project_id=document["project_id"],
            document_id=document_id,
        )
        if is_cancel_requested():
            delete_document(
                filename=document["filename"],
                user_id=document["user_id"],
                project_id=document["project_id"],
                document_id=document_id,
            )
            document_repo.mark_cancelled(document_id, utc_now())
            raise InterruptedError("文档索引任务已取消")
        update_progress(90, "正在保存文档索引状态")
        marked_ready = document_repo.mark_ready(document_id, chunks_count, utc_now(), utc_now())
        if not marked_ready:
            # 删除请求可能与此处并发；避免出现“数据库已删除但向量仍残留”。
            delete_document(
                filename=document["filename"],
                user_id=document["user_id"],
                project_id=document["project_id"],
                document_id=document_id,
            )
            raise InterruptedError("文档已被删除")
        update_progress(100, "文档索引已完成")
        return {"document_id": document_id, "filename": document["filename"], "chunks_count": chunks_count}
    except InterruptedError:
        raise
    except Exception as exc:
        document_repo.mark_failed(document_id, str(exc), utc_now())
        raise


def list_documents_for_user(user_id: int, project_id: int | None = None) -> list[dict[str, Any]]:
    if project_id is not None and project_repo.get_by_id(user_id, project_id) is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return document_repo.list_for_user(user_id, project_id)


def delete_document_for_user(user_id: int, document_id: str) -> dict[str, Any]:
    document = document_repo.get(document_id, user_id)
    if document is None or document["status"] == "deleted":
        raise HTTPException(status_code=404, detail="文档不存在")
    if document["job_id"]:
        job_repo.request_cancel(user_id, document["job_id"], utc_now())
    deleted = document_repo.mark_deleted(document_id, utc_now())
    if deleted is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    delete_document(
        filename=document["filename"],
        user_id=user_id,
        project_id=document["project_id"],
        document_id=document_id,
    )
    _remove_file(document["storage_path"])
    return {"status": "success", "message": f"已删除文档：{document['filename']}", "document": deleted}


def enqueue_reindex(user_id: int, document_id: str) -> dict[str, Any]:
    document = document_repo.get(document_id, user_id)
    if document is None or document["status"] == "deleted":
        raise HTTPException(status_code=404, detail="文档不存在")
    if document["status"] in {"queued", "processing"}:
        raise HTTPException(status_code=409, detail="文档已有索引任务正在执行")
    if not document_repo.queue_for_retry(document_id, utc_now()):
        raise HTTPException(status_code=409, detail="文档状态已变化，请稍后重试")
    try:
        job = create_job(
            user_id=user_id,
            job_type="document_reindex",
            payload={"document_id": document_id},
            project_id=document["project_id"],
        )
    except Exception:
        document_repo.mark_failed(document_id, "重新索引任务创建失败", utc_now())
        raise
    # 失败状态允许重新排队；job_id 被更新为本次最新任务。
    with_job = document_repo.set_job_id(document_id, job["id"], utc_now())
    if not with_job:
        raise HTTPException(status_code=409, detail="文档状态已变化，请稍后重试")
    return {
        "status": "accepted",
        "message": "已创建重新索引任务",
        "document": document_repo.get(document_id, user_id),
        "job": job,
    }
