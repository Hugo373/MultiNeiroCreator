"""助手服务：profile、对话历史、RAG 文档管理。

对话主流程已拆往 services/chat/（C2）：
- context_builder：备菜（附件/RAG 上下文、消息组装）
- tool_executor：跑腿（安全执行工具，永不抛异常）
- chat_orchestrator：编排（多轮工具循环、流式输出、持久化）
"""

import asyncio
import logging
import os
import tempfile

from fastapi import UploadFile

from repositories.chat_repo import clear_history as repo_clear_history
from repositories.chat_repo import list_history
from repositories.user_repo import get_profile, update_profile
from services.rag import (
    delete_document,
    list_documents,
    reindex_document,
    replace_document,
)

logger = logging.getLogger("assistant")


def load_profile(user_id: int) -> str:
    return get_profile(user_id)


def save_profile(user_id: int, profile: str) -> None:
    update_profile(user_id, profile)


def get_history(user_id: int, project_id: int | None = None) -> list[dict]:
    return list_history(user_id, project_id)


def clear_history(user_id: int, project_id: int | None = None) -> dict:
    repo_clear_history(user_id, project_id)
    return {"status": "ok"}


async def upload_document(file: UploadFile, user_id: int, project_id: int | None = None) -> dict:
    tmp_path = None
    try:
        suffix = os.path.splitext(file.filename or "")[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        chunks_count = await asyncio.to_thread(
            replace_document,
            tmp_path,
            file.filename or "upload.txt",
            user_id,
            project_id,
        )
        return {"status": "success", "message": f"成功导入文档: {file.filename}（共分切成 {chunks_count} 块）"}
    except Exception as exc:
        logger.exception(
            "文档导入失败",
            extra={"evt": "doc_import_error", "error_type": type(exc).__name__},
        )
        return {"status": "error", "message": f"导入失败: {exc!s}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def get_rag_documents(user_id: int, project_id: int | None = None) -> list[dict]:
    return list_documents(user_id=user_id, project_id=project_id)


def remove_rag_document(filename: str, user_id: int, project_id: int | None = None) -> dict:
    deleted_count = delete_document(filename=filename, user_id=user_id, project_id=project_id)
    if deleted_count == 0:
        return {"status": "error", "message": f"未找到文档: {filename}"}
    return {"status": "success", "message": f"已删除文档: {filename}", "deleted_chunks": deleted_count}


def rebuild_rag_document(filename: str, user_id: int, project_id: int | None = None) -> dict:
    chunks_count = reindex_document(filename=filename, user_id=user_id, project_id=project_id)
    return {"status": "success", "message": f"已重建文档索引: {filename}", "chunks_count": chunks_count}
