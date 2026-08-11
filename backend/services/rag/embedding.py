import logging
import time

from google import genai

from core.config import EMBEDDING_API_KEY

logger = logging.getLogger("rag.embedding")

EMBEDDING_MODEL = "gemini-embedding-001"

client_ai = (
    genai.Client(api_key=EMBEDDING_API_KEY)
    if EMBEDDING_API_KEY
    else None
)


def get_embedding(text: str):
    if client_ai is None:
        raise RuntimeError("未配置 API_KEY，RAG 向量检索暂不可用")

    started = time.perf_counter()
    try:
        result = client_ai.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )
    except Exception as exc:
        logger.error(
            "查询向量化失败: %s", type(exc).__name__,
            extra={"evt": "embed_query_error", "error_type": type(exc).__name__,
                   "text_chars": len(text)},
        )
        raise
    logger.info(
        "查询向量化完成",
        extra={"evt": "embed_query", "model": EMBEDDING_MODEL, "text_chars": len(text),
               "duration_ms": round((time.perf_counter() - started) * 1000, 1)},
    )
    return result.embeddings[0].values


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    if client_ai is None:
        raise RuntimeError("未配置 API_KEY，文档向量化暂不可用")

    started = time.perf_counter()
    embeddings = []

    # 串行逐条调用是已知性能债（G1），这里先把耗时记下来，压测时好对比优化前后
    for index, text in enumerate(texts):
        try:
            result = client_ai.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
            )
        except Exception as exc:
            logger.error(
                "批量向量化失败: %s", type(exc).__name__,
                extra={"evt": "embed_batch_error", "error_type": type(exc).__name__,
                       "failed_index": index, "total_chunks": len(texts)},
            )
            raise
        embeddings.append(result.embeddings[0].values)

    logger.info(
        "批量向量化完成",
        extra={"evt": "embed_batch", "model": EMBEDDING_MODEL, "chunks": len(texts),
               "duration_ms": round((time.perf_counter() - started) * 1000, 1)},
    )
    return embeddings
