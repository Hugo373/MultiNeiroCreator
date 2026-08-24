"""助手服务：profile、对话历史、RAG 文档查询。

文档上传/索引使用 E3 持久化任务：上传请求只负责保存原文件并创建 job，
解析、chunk、embedding 和 Chroma 写入全部由独立 Worker 完成。
"""

from repositories.chat_repo import clear_history as repo_clear_history
from repositories.chat_repo import list_history
from repositories.document_repo import get as get_document
from repositories.user_repo import get_profile, update_profile
from services.document_service import (
    delete_document_for_user,
    enqueue_reindex,
    enqueue_upload,
    list_documents_for_user,
)


def load_profile(user_id: int) -> str:
    return get_profile(user_id)


def save_profile(user_id: int, profile: str) -> None:
    update_profile(user_id, profile)


def get_history(user_id: int, project_id: int | None = None) -> list[dict]:
    return list_history(user_id, project_id)


def clear_history(user_id: int, project_id: int | None = None) -> dict:
    repo_clear_history(user_id, project_id)
    return {"status": "ok"}


async def upload_document(file, user_id: int, project_id: int | None = None, size_bytes: int = 0) -> dict:
    return await enqueue_upload(file, user_id, project_id, size_bytes)


def get_rag_documents(user_id: int, project_id: int | None = None) -> list[dict]:
    return list_documents_for_user(user_id=user_id, project_id=project_id)


def remove_rag_document(
    filename: str | None,
    user_id: int,
    project_id: int | None = None,
    document_id: str | None = None,
) -> dict:
    if document_id is None and filename is not None:
        candidates = [
            item for item in list_documents_for_user(user_id, project_id) if item["filename"] == filename
        ]
        if not candidates:
            return {"status": "error", "message": f"未找到文档: {filename}"}
        document_id = candidates[0]["id"]
    if document_id is None:
        return {"status": "error", "message": "未提供文档身份"}
    return delete_document_for_user(user_id, document_id)


def rebuild_rag_document(
    filename: str | None,
    user_id: int,
    project_id: int | None = None,
    document_id: str | None = None,
) -> dict:
    if document_id is None and filename is not None:
        candidates = [
            item for item in list_documents_for_user(user_id, project_id) if item["filename"] == filename
        ]
        if not candidates:
            return {"status": "error", "message": f"未找到文档: {filename}"}
        document_id = candidates[0]["id"]
    if document_id is None or get_document(document_id, user_id) is None:
        return {"status": "error", "message": "未找到文档"}
    return enqueue_reindex(user_id, document_id)
