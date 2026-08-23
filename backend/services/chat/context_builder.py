"""上下文构建器（C2 拆分件之二）：负责"备菜"——组装喂给模型的 messages。

职责边界（按消费者划分）：
- messages 的消费者是**模型** → 这里负责：system prompt、附件上下文、RAG 检索、
  服务端历史裁剪、附件标注，全部在此完成；
- clean_history 的消费者是**前端**（done 事件）→ 一并在组装时顺产，编排器不再关心格式。

纯函数 assemble_messages 与做 IO 的 build_chat_context 分开：消息构建顺序可以
不碰数据库直接单测。
"""

import asyncio
import logging
import time
from dataclasses import dataclass

from agents.neyria import build_system_prompt
from core import config
from repositories.chat_repo import list_history
from repositories.user_repo import get_profile
from services.rag import get_document_chunks, search

MAX_ATTACHMENT_CONTEXT_CHARS = 12000
MAX_RETRIEVED_CONTEXT_CHARS = 6000

logger = logging.getLogger("assistant")


@dataclass
class ChatContext:
    """一次对话所需的全部上下文成品。"""

    messages: list[dict]  # 喂模型：system + 裁剪后历史 + 本条用户消息
    clean_history: list[dict]  # 回前端：done 事件里的干净历史（含本条用户消息）
    persist_text: str  # 持久化用的用户消息文本（空消息回落"已发送附件"）
    attachments: list[dict]  # 规范化后的本条附件
    has_knowledge_context: bool = False  # 是否检索到可供模型使用的私有资料


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


def assemble_messages(
    system_prompt: str,
    history: list[dict],
    message: str,
    attachments: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """纯函数：把各层素材按固定顺序拼成 (messages, clean_history)。

    顺序契约：system 最前 → 合法历史（过滤非 user/assistant 角色与空内容）→
    本条用户消息最后。历史与本条消息若带附件，模型侧内容追加附件标注。
    """
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
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
        history_item: dict = {"role": role, "content": content}
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
    current_user_history_item: dict = {"role": "user", "content": message}
    if normalized_attachments:
        current_user_history_item["attachments"] = normalized_attachments
    clean_history.append(current_user_history_item)

    return messages, clean_history


async def build_chat_context(
    user_id: int,
    message: str,
    project_id: int | None = None,
    attachments: list[dict] | None = None,
) -> ChatContext:
    """做 IO 的入口：并行取 RAG 上下文与 profile/历史，产出 ChatContext。"""
    rag_started = time.perf_counter()
    try:
        attachment_context, retrieved_context = await asyncio.gather(
            asyncio.to_thread(build_attachment_context, user_id, project_id, attachments),
            asyncio.to_thread(build_retrieved_context, user_id, message, project_id),
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
        # 降级不降噪：RAG 挂了对话仍可用，但必须留痕，否则检索失效只会表现为"回答质量变差"
        logger.warning(
            "上下文构建失败，降级为无 RAG 上下文: %s", type(exc).__name__, exc_info=True,
            extra={"evt": "context_build_error", "error_type": type(exc).__name__},
        )
        context = ""

    # 同步 DB 读丢线程池：SSE 生成器调用链上任何同步调用都在占用事件循环（C1）
    profile, full_history = await asyncio.gather(
        asyncio.to_thread(get_profile, user_id),
        asyncio.to_thread(list_history, user_id, project_id),
    )
    system_prompt = build_system_prompt(profile, context)

    # 对话历史以服务端数据库为唯一真源，不信任客户端传来的内容（防伪造上下文注入）
    history = full_history[-config.CHAT_HISTORY_MAX_ITEMS:]

    messages, clean_history = assemble_messages(system_prompt, history, message, attachments)
    persist_text = message if (message or "").strip() else "已发送附件"
    # done 事件与持久化保持同一份文本：空消息统一显示"已发送附件"
    clean_history[-1]["content"] = persist_text

    return ChatContext(
        messages=messages,
        clean_history=clean_history,
        persist_text=persist_text,
        attachments=normalize_attachments(attachments),
        has_knowledge_context=bool(context),
    )
