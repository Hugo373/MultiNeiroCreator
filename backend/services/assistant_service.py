import asyncio
import json
import logging
import os
import tempfile
import time
from collections.abc import AsyncGenerator

from fastapi import HTTPException, UploadFile
from starlette.concurrency import iterate_in_threadpool

from agents.neyria import build_system_prompt, client, tools_map, tools_schema
from core import config
from repositories.chat_repo import append_message, list_history
from repositories.chat_repo import clear_history as repo_clear_history
from repositories.user_repo import get_profile, update_profile
from services.rag import (
    delete_document,
    get_document_chunks,
    list_documents,
    reindex_document,
    replace_document,
    search,
)

MAX_ATTACHMENT_CONTEXT_CHARS = 12000
MAX_RETRIEVED_CONTEXT_CHARS = 6000

MAX_TOOL_ARG_LENGTH = 500

CHAT_MODEL = "glm-4-flash"  # E4 会把模型名收进 config，先收敛到单一常量

logger = logging.getLogger("assistant")


def validate_tool_call(func_name: str, func_args: dict) -> str | None:
    """校验模型返回的工具调用，返回错误信息；合法时返回 None。"""
    if func_name not in tools_map:
        return f"不支持的工具: {func_name}"
    if not isinstance(func_args, dict):
        return "工具参数格式错误"
    for value in func_args.values():
        if isinstance(value, str) and len(value) > MAX_TOOL_ARG_LENGTH:
            return "工具参数过长"
    return None


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


def extract_stream_content(chunk) -> str:
    if not chunk.choices:
        return ""

    delta = chunk.choices[0].delta
    return delta.content if hasattr(delta, "content") and delta.content else ""


def normalize_attachments(attachments: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for attachment in attachments or []:
        name = str(attachment.get("name", "")).strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "kind": attachment.get("kind"),
                "badge": attachment.get("badge"),
                "meta": attachment.get("meta"),
            }
        )
    return normalized


def format_message_content_for_model(content: str, attachments: list[dict] | None = None) -> str:
    normalized_attachments = normalize_attachments(attachments)
    if not normalized_attachments:
        return content

    attachment_names = "、".join(item["name"] for item in normalized_attachments)
    base_content = (content or "").strip() or "用户发送了附件，请结合附件内容处理本条请求。"
    return f"{base_content}\n\n[该条消息附带文件：{attachment_names}]"


def build_attachment_context(
    user_id: int,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> str:
    normalized_attachments = normalize_attachments(attachments)
    if not normalized_attachments:
        return ""

    sections: list[str] = []
    consumed = 0
    for attachment in normalized_attachments:
        chunks = get_document_chunks(
            filename=attachment["name"],
            user_id=user_id,
            project_id=project_id,
        )
        if not chunks:
            continue

        remaining = MAX_ATTACHMENT_CONTEXT_CHARS - consumed
        if remaining <= 0:
            break

        content = "\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()
        if not content:
            continue

        snippet = content[:remaining]
        sections.append(f"[附件 {attachment['name']}]\n{snippet}")
        consumed += len(snippet)

    return "\n\n".join(sections)


def build_retrieved_context(
    user_id: int,
    message: str,
    project_id: int | None = None,
) -> str:
    if not (message or "").strip():
        return ""

    docs = search(message, n_results=3, user_id=user_id, project_id=project_id)
    if not docs:
        return ""

    joined = "\n".join(doc.strip() for doc in docs if doc.strip()).strip()
    return joined[:MAX_RETRIEVED_CONTEXT_CHARS] if joined else ""


async def stream_chat(
    user: dict,
    message: str,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """对话流外层：兼做流中断兜底。

    SSE 响应头发出后全局异常 handler 就管不到了（无法再发 500），生成器里的
    异常只会表现为前端断流。这里统一兼做：记结构化错误日志 + 向前端发一条
    error 事件体面收尾（前端对未知类型静默忽略，兼容旧版本）。
    """
    started = time.perf_counter()
    try:
        async for event in _stream_chat_impl(user, message, project_id, attachments):
            yield event
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "对话流中断: %s", type(exc).__name__,
            extra={
                "evt": "chat_stream_error",
                "error_type": type(exc).__name__,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        yield f"data: {json.dumps({'type': 'error', 'message': '服务器开小差了，请稍后重试'}, ensure_ascii=False)}\n\n"


async def _stream_chat_impl(
    user: dict,
    message: str,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    if client is None:
        raise HTTPException(status_code=503, detail="未配置 API_KEY，聊天功能暂不可用")

    chat_started = time.perf_counter()
    display_message = (message or "").strip() or "已发送附件"

    rag_started = time.perf_counter()
    try:
        attachment_context, retrieved_context = await asyncio.gather(
            asyncio.to_thread(build_attachment_context, user["id"], project_id, attachments),
            asyncio.to_thread(build_retrieved_context, user["id"], message, project_id),
        )
        context_sections = [item for item in [attachment_context, retrieved_context] if item]
        context = "\n\n".join(context_sections)
        logger.info(
            "上下文构建完成",
            extra={
                "evt": "context_build",
                "duration_ms": round((time.perf_counter() - rag_started) * 1000, 1),
                "attachment_chars": len(attachment_context),
                "retrieved_chars": len(retrieved_context),
            },
        )
    except Exception as exc:
        # 降级不降噪：RAG 挂了对话仍可用，但必须留痕，否则检索失效只会表现为“回答质量变差”
        logger.warning(
            "上下文构建失败，降级为无 RAG 上下文: %s", type(exc).__name__, exc_info=True,
            extra={"evt": "context_build_error", "error_type": type(exc).__name__},
        )
        context = ""

    # 同步 DB 读也丢线程池：SSE 生成器里任何同步调用都在占用事件循环（C1）
    profile, full_history = await asyncio.gather(
        asyncio.to_thread(load_profile, user["id"]),
        asyncio.to_thread(list_history, user["id"], project_id),
    )
    system_prompt = build_system_prompt(profile, context)

    # 对话历史以服务端数据库为唯一真源，不信任客户端传来的内容（防伪造上下文注入）
    history = full_history[-config.CHAT_HISTORY_MAX_ITEMS:]

    messages = [{"role": "system", "content": system_prompt}]
    clean_history: list[dict] = []
    for item in history:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        normalized_history_attachments = normalize_attachments(item.get("attachments"))
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append(
            {
                "role": role,
                "content": format_message_content_for_model(content, normalized_history_attachments),
            }
        )
        history_item = {"role": role, "content": content}
        if normalized_history_attachments:
            history_item["attachments"] = normalized_history_attachments
        clean_history.append(history_item)

    normalized_attachments = normalize_attachments(attachments)
    messages.append(
        {
            "role": "user",
            "content": format_message_content_for_model(message, normalized_attachments),
        }
    )
    current_user_history_item = {"role": "user", "content": message}
    if normalized_attachments:
        current_user_history_item["attachments"] = normalized_attachments
    clean_history.append(current_user_history_item)

    func_name = None
    reply = ""

    llm_started = time.perf_counter()
    first_token_at: float | None = None

    first_stream = await asyncio.to_thread(
        client.chat.completions.create,
        model=CHAT_MODEL,
        messages=messages,
        tools=tools_schema,
        stream=True,
    )

    tool_call_id = ""
    func_args_raw = ""

    # 上游流必须在线程池里迭代：同步 for 会阻塞事件循环，uvloop 下已 write 的
    # 字节要等循环空闲才刷出 socket，SSE 会退化成"生成完一次性吐出"（连响应头都被扣住）
    async for chunk in iterate_in_threadpool(first_stream):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        tool_call_deltas = getattr(delta, "tool_calls", None)
        if tool_call_deltas:
            tool_call = tool_call_deltas[0]
            tool_call_id = tool_call.id or tool_call_id
            if tool_call.function:
                func_name = tool_call.function.name or func_name
                func_args_raw += tool_call.function.arguments or ""
            continue
        content = delta.content if getattr(delta, "content", None) else ""
        if content:
            if first_token_at is None:
                first_token_at = time.perf_counter()
            reply += content
            yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"

    if func_name:
        try:
            func_args = json.loads(func_args_raw)
        except (json.JSONDecodeError, TypeError):
            func_args = None
        validation_error = (
            "工具参数解析失败" if func_args is None else validate_tool_call(func_name, func_args)
        )
        yield f"data: {json.dumps({'type': 'tool', 'tool_name': func_name}, ensure_ascii=False)}\n\n"
        tool_started = time.perf_counter()
        if validation_error:
            result = f"工具调用被拒绝：{validation_error}"
            logger.warning(
                "工具调用被拒绝: %s", validation_error,
                extra={"evt": "tool_rejected", "tool": func_name, "reason": validation_error},
            )
        else:
            try:
                # 同步工具（如联网搜索可阻塞 5s+）必须丢线程池，否则阻塞事件循环拖死其他用户的 SSE
                result = await asyncio.to_thread(tools_map[func_name].invoke, func_args)
                logger.info(
                    "工具调用完成",
                    extra={
                        "evt": "tool_call",
                        "tool": func_name,
                        "duration_ms": round((time.perf_counter() - tool_started) * 1000, 1),
                        "result_chars": len(str(result)),
                    },
                )
            except Exception as exc:
                logger.exception(
                    "工具执行失败: %s", type(exc).__name__,
                    extra={
                        "evt": "tool_error",
                        "tool": func_name,
                        "error_type": type(exc).__name__,
                        "duration_ms": round((time.perf_counter() - tool_started) * 1000, 1),
                    },
                )
                result = "工具执行失败，请换个方式提问或稍后重试。"
        messages.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {"name": func_name, "arguments": func_args_raw},
                    }
                ],
            }
        )
        messages.append({"role": "tool", "content": result, "tool_call_id": tool_call_id})
        final_stream = await asyncio.to_thread(
            client.chat.completions.create,
            model=CHAT_MODEL,
            messages=messages,
            stream=True,
        )
        async for chunk in iterate_in_threadpool(final_stream):
            content = extract_stream_content(chunk)
            if content:
                if first_token_at is None:
                    first_token_at = time.perf_counter()
                reply += content
                yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"

    messages.append({"role": "assistant", "content": reply})
    if not (message or "").strip():
        current_user_history_item["content"] = display_message
    await asyncio.to_thread(
        append_message,
        user["id"], "user", current_user_history_item["content"], project_id, normalized_attachments,
    )
    await asyncio.to_thread(append_message, user["id"], "assistant", reply, project_id)
    clean_history.append({"role": "assistant", "content": reply})
    now = time.perf_counter()
    logger.info(
        "对话完成",
        extra={
            "evt": "chat_done",
            "model": CHAT_MODEL,
            "tool": func_name,
            "history_items": len(clean_history),
            "reply_chars": len(reply),
            # TTFT 从首次请求 LLM 算起；若走了工具分支，包含工具耗时（用户体感口径）
            "ttft_ms": round(((first_token_at or now) - llm_started) * 1000, 1),
            "llm_ms": round((now - llm_started) * 1000, 1),
            "total_ms": round((now - chat_started) * 1000, 1),
        },
    )
    yield f"data: {json.dumps({'type': 'done', 'history': clean_history, 'tool_used': func_name}, ensure_ascii=False)}\n\n"
