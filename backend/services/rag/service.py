from typing import Any

from core.config import RAG_DISTANCE_THRESHOLD
from services.rag.embedding import get_embedding, get_embeddings_batch
from services.rag.parser import chunk_text, read_file
from services.rag.retriever import (
    add_indexed_document,
    delete_indexed_document,
    get_indexed_document_chunks,
    list_indexed_documents,
    retrieve_document_hits,
    retrieve_documents,
)


def add_document(
    file_path: str,
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    replace_existing: bool = True,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    document_id: str | None = None,
) -> int:
    text = read_file(file_path, filename)
    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        raise ValueError("文档未切分出有效文本块，无法写入知识库")
    embeddings = get_embeddings_batch(chunks)
    return add_indexed_document(
        filename=filename,
        chunks=chunks,
        embeddings=embeddings,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        replace_existing=replace_existing,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        document_id=document_id,
    )


def replace_document(
    file_path: str,
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    document_id: str | None = None,
) -> int:
    return add_document(
        file_path=file_path,
        filename=filename,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        replace_existing=True,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        document_id=document_id,
    )


def search(
    query: str,
    n_results: int = 3,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[str]:
    embedding = get_embedding(query)
    return retrieve_documents(
        query_embedding=embedding,
        n_results=n_results,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        max_distance=RAG_DISTANCE_THRESHOLD,
    )


def search_with_metadata(
    query: str,
    n_results: int = 3,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[dict[str, Any]]:
    embedding = get_embedding(query)
    return retrieve_document_hits(
        query_embedding=embedding,
        n_results=n_results,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        max_distance=RAG_DISTANCE_THRESHOLD,
    )


def list_documents(
    limit: int = 100,
    offset: int = 0,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
) -> list[dict]:
    return list_indexed_documents(
        limit=limit,
        offset=offset,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
    )


def delete_document(
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    document_id: str | None = None,
) -> int:
    return delete_indexed_document(
        filename=filename,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        document_id=document_id,
    )


def reindex_document(
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    document_id: str | None = None,
) -> int:
    chunks = get_indexed_document_chunks(
        filename=filename,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        document_id=document_id,
    )
    if not chunks:
        raise ValueError(f"未找到文档：{filename}")

    embeddings = get_embeddings_batch(chunks)
    return add_indexed_document(
        filename=filename,
        chunks=chunks,
        embeddings=embeddings,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        replace_existing=True,
        document_id=document_id,
    )


def get_document_chunks(
    filename: str,
    user_id: int | None = None,
    project_id: int | None = None,
    scope: str = "assistant",
    document_id: str | None = None,
) -> list[str]:
    return get_indexed_document_chunks(
        filename=filename,
        user_id=user_id,
        project_id=project_id,
        scope=scope,
        document_id=document_id,
    )
