import hashlib
from typing import Any

from services.rag.vectorstore import vectorstore


def _build_chunk_ids(
    filename: str,
    chunk_count: int,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    document_id: str | None = None,
) -> list[str]:
    return [
        hashlib.md5(f"{filename}:{document_id}:{user_id}:{project_id}:{scope}:{index}".encode()).hexdigest()
        for index in range(chunk_count)
    ]


def _build_chunk_metadatas(
    filename: str,
    chunk_count: int,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    document_id: str | None = None,
) -> list[dict]:
    return [
        {
            "source": filename,
            # legacy chunks没有文档 ID；新任务必须写入真实 ID，删除/替换时才能精确清理。
            "document_id": document_id or "legacy",
            "user_id": user_id if user_id is not None else -1,
            "project_id": project_id if project_id is not None else -1,
            "scope": scope,
            "chunk_index": index,
            "chunk_count": chunk_count,
            "chunk_size": chunk_size if chunk_size is not None else -1,
            "chunk_overlap": chunk_overlap if chunk_overlap is not None else -1,
        }
        for index in range(chunk_count)
    ]


def add_indexed_document(
    filename: str,
    chunks: list[str],
    embeddings: list,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    replace_existing: bool = True,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    document_id: str | None = None,
) -> int:
    if replace_existing:
        vectorstore.delete_documents(
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            source=filename,
            document_id=document_id,
        )

    chunk_count = len(chunks)
    metadatas = _build_chunk_metadatas(
        filename=filename,
        chunk_count=chunk_count,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        document_id=document_id,
    )
    ids = _build_chunk_ids(
        filename=filename,
        chunk_count=chunk_count,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        document_id=document_id,
    )
    vectorstore.add_documents(
        documents=chunks,
        embeddings=embeddings,
        ids=ids,
        metadatas=metadatas,
    )
    return chunk_count


def list_indexed_documents(
    limit: int = 100,
    offset: int = 0,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[dict]:
    results = vectorstore.get_documents(user_id=user_id, project_id=project_id, scope=scope)
    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []

    grouped: dict[tuple[str, int, int, str, str], dict] = {}
    for metadata, document in zip(metadatas, documents, strict=False):
        key = (
            str(metadata.get("source", "")),
            int(metadata.get("user_id", -1)),
            int(metadata.get("project_id", -1)),
            str(metadata.get("scope", scope)),
            str(metadata.get("document_id", "legacy")),
        )
        item = grouped.get(key)
        if item is None:
            preview = (document or "").replace("\n", " ").strip()
            grouped[key] = {
                "filename": metadata.get("source", ""),
                "document_id": metadata.get("document_id"),
                "user_id": metadata.get("user_id", -1),
                "project_id": metadata.get("project_id", -1),
                "scope": metadata.get("scope", scope),
                "chunk_count": 1,
                "chunk_size": metadata.get("chunk_size", -1),
                "chunk_overlap": metadata.get("chunk_overlap", -1),
                "preview": preview[:160],
            }
            continue
        item["chunk_count"] += 1

    documents_list = list(grouped.values())
    documents_list.sort(key=lambda item: str(item["filename"]).lower())
    return documents_list[offset : offset + limit]


def delete_indexed_document(
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    document_id: str | None = None,
) -> int:
    results = vectorstore.get_documents(
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        source=filename if document_id is None else None,
        document_id=document_id,
    )
    ids = results.get("ids") or []
    if not ids:
        return 0

    vectorstore.delete_documents(ids=ids)
    return len(ids)


def get_indexed_document_chunks(
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    document_id: str | None = None,
) -> list[str]:
    results = vectorstore.get_documents(
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        source=filename if document_id is None else None,
        document_id=document_id,
    )
    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []
    ordered_chunks = sorted(
        zip(metadatas, documents, strict=False),
        key=lambda item: int(item[0].get("chunk_index", 0)),
    )
    return [document for _, document in ordered_chunks]


def get_indexed_document_hits(
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    document_id: str | None = None,
) -> list[dict[str, Any]]:
    results = vectorstore.get_documents(
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        source=filename if document_id is None else None,
        document_id=document_id,
    )
    metadatas = results.get("metadatas") or []
    documents = results.get("documents") or []
    ordered = sorted(
        zip(metadatas, documents, strict=False),
        key=lambda item: int(item[0].get("chunk_index", 0)),
    )
    return [
        {
            "content": document,
            "source": metadata.get("source", filename),
            "document_id": metadata.get("document_id"),
            "chunk_index": int(metadata.get("chunk_index", 0)),
            "chunk_count": int(metadata.get("chunk_count", 0)),
        }
        for metadata, document in ordered
    ]


def _filter_by_distance(
    documents: list[str],
    distances: list[float] | None,
    max_distance: float | None,
) -> list[str]:
    """只保留距离足够近的 chunk；没有距离时不把结果伪装成命中。"""
    if max_distance is None:
        return documents
    if not distances:
        return []
    return [
        document
        for document, distance in zip(documents, distances, strict=False)
        if isinstance(distance, (int, float)) and distance <= max_distance
    ]


def retrieve_document_hits(
    query_embedding: Any,
    n_results: int = 3,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    max_distance: float | None = None,
) -> list[dict[str, Any]]:
    """返回带来源元数据的召回结果，供引用展示和审计使用。"""
    available = vectorstore.count()
    if available == 0:
        return []
    results = vectorstore.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, available),
        user_id=user_id,
        project_id=project_id,
        scope=scope,
    )
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]
    if not documents:
        return []

    hits: list[dict[str, Any]] = []
    for document, metadata, distance in zip(documents, metadatas, distances, strict=False):
        if max_distance is not None and (not isinstance(distance, (int, float)) or distance > max_distance):
            continue
        hits.append(
            {
                "content": document,
                "source": metadata.get("source", "未知文档"),
                "document_id": metadata.get("document_id"),
                "chunk_index": int(metadata.get("chunk_index", 0)),
                "chunk_count": int(metadata.get("chunk_count", 0)),
                "distance": distance,
            }
        )
    return hits


def retrieve_documents(
    query_embedding: Any,
    n_results: int = 3,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    max_distance: float | None = None,
) -> list[str]:
    return [
        hit["content"]
        for hit in retrieve_document_hits(
            query_embedding=query_embedding,
            n_results=n_results,
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            max_distance=max_distance,
        )
    ]
