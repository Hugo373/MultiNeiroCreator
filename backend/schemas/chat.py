from typing import List

from pydantic import BaseModel, Field

from core import config


class ChatAttachment(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    kind: str | None = Field(default=None, max_length=100)
    badge: str | None = Field(default=None, max_length=100)
    meta: str | None = Field(default=None, max_length=255)


class ChatRequest(BaseModel):
    # 注意：不接收 history——对话历史以服务端数据库为唯一真源（A5），客户端多传的字段会被忽略
    message: str = Field(..., max_length=config.CHAT_MESSAGE_MAX_CHARS)
    project_id: int | None = None
    attachments: List[ChatAttachment] = Field(
        default_factory=list, max_length=config.CHAT_ATTACHMENTS_MAX_ITEMS
    )


class ProfileRequest(BaseModel):
    profile: str = Field(..., max_length=config.PROFILE_MAX_CHARS)


class RagDocumentDeleteRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    project_id: int | None = None
