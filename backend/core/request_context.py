"""请求上下文中间件：request_id 传播 + access log。

用纯 ASGI 中间件而不是 BaseHTTPMiddleware：后者会把响应包一层缓冲，
/chat 的 SSE 逐 token 流式（solved.md #18 修好的）会被破坏。

职责：
1. 读取客户端传来的 X-Request-ID（限长防注入），没有则生成 8 位随机 id；
2. 写入 request_id ContextVar，让本请求内所有日志自动携带；
3. 在响应头回传 X-Request-ID，前端报障时报这个 id 即可定位全链路日志；
4. 响应体发送完毕后记一条 access log（对 SSE 意味着计入整个流式时长）；
5. 未处理异常继续向外抛（由 main.py 的兜底 handler 生成 500 响应），
   但先记下 status=500 的 access line，保证异常请求也有访问记录。

user_id 不在这里解析：鉴权统一走 core/security.decode_token，成功后由它写入
user_id ContextVar，这里只负责读——避免中间件重复解一遍 JWT。
"""
import logging
import time
import uuid

from core.logging_config import request_id_var, user_id_var

logger = logging.getLogger("access")


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = ""
        for name, value in scope["headers"]:
            if name == b"x-request-id":
                incoming = value.decode("latin-1")[:64].strip()
                break
        request_id = incoming or uuid.uuid4().hex[:8]
        request_id_var.set(request_id)
        user_id_var.set("-")

        start = time.perf_counter()
        status_code = 0

        async def wrapped_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        except Exception:
            # 兜底 handler 在本中间件外层（ServerErrorMiddleware），异常必须继续外抛；
            # 此时响应不经过 wrapped_send，access line 在这里补记
            self._log(scope, 500, start)
            raise
        else:
            self._log(scope, status_code, start)

    def _log(self, scope, status_code: int, start: float) -> None:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        method = scope["method"]
        path = scope["path"]
        level = logging.WARNING if status_code >= 500 else logging.INFO
        logger.log(
            level,
            "%s %s -> %s (%sms)",
            method,
            path,
            status_code,
            duration_ms,
            extra={"evt": "access", "method": method, "path": path,
                   "status": status_code, "duration_ms": duration_ms},
        )
