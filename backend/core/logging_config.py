"""结构化日志基础设施。

设计：
- 标准库 logging + contextvars，零第三方依赖；
- request_id / user_id 存 ContextVar（请求作用域，async 并发下天然隔离），
  由 RequestContextFilter 注入每条 LogRecord，业务代码打日志时无需手动传；
- 开发环境输出单行可读格式，生产环境（IS_PRODUCTION）输出 JSON，方便日志采集；
- 额外的结构化字段统一通过 `logger.info("...", extra={"evt": ..., ...})` 传入，
  JSON 模式下会平铺进日志对象，开发模式下拼接为 key=value 尾巴。

脱敏红线（团队约定，写测试时会断言）：
- 不记录：密码、token、验证码、用户消息正文、文档内容；
- 只记录：长度、数量、耗时、状态码、模型名、工具名等元信息。
"""
import json
import logging
import sys
from contextvars import ContextVar

from core.config import IS_PRODUCTION

# 请求作用域上下文：request_context 中间件写 request_id，decode_token 写 user_id
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

# LogRecord 自带的属性名集合，用于把 extra={} 传入的自定义字段挑出来
_RESERVED_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()
) | {"request_id", "user_id", "taskName", "message", "asctime"}


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        return True


def _extra_fields(record: logging.LogRecord) -> dict:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED_ATTRS and not key.startswith("_")
    }


class DevFormatter(logging.Formatter):
    """开发环境：单行可读，自定义字段以 key=value 追加在行尾。"""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{self.formatTime(record, '%H:%M:%S')} "
            f"{record.levelname:<7} [{record.request_id}] "
            f"{record.name}: {record.getMessage()}"
        )
        extras = _extra_fields(record)
        if record.user_id != "-":
            extras = {"user_id": record.user_id, **extras}
        if extras:
            base += " | " + " ".join(f"{k}={v}" for k, v in extras.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


class JsonFormatter(logging.Formatter):
    """生产环境：每行一个 JSON 对象。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": record.request_id,
            "user_id": record.user_id,
            "message": record.getMessage(),
            **_extra_fields(record),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if IS_PRODUCTION else DevFormatter())
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.handlers.clear()  # 覆盖 uvicorn/basicConfig 可能已装的 handler，避免重复输出
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # 降噪：第三方库的 INFO 没有排障价值
    for noisy in ("httpx", "httpcore", "chromadb", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # uvicorn 的 error 日志沿用我们的 handler；access 日志关掉（由 request_context 中间件
    # 记带 request_id/耗时/user_id 的 access line，信息量是 uvicorn 默认格式的超集）
    logging.getLogger("uvicorn.access").disabled = True
