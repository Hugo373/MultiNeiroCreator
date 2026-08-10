"""全局请求体大小限制中间件。

为什么必须做在中间件层：Starlette 会先把整个请求体读进内存，然后才轮到
Pydantic 校验——字段上的 max_length 拦不住一个 1GB 的原始 body，检查必须
发生在"读"这一侧。

两道防线：
1. 带 Content-Length 的请求：读 header 就能判断，超限直接 413，一个字节都不收；
2. 不带 Content-Length 的分块传输（chunked）：header 可以撒谎/缺失，只能在
   wrapped_receive 里对实际收到的字节累计计数。超限时不能靠向应用抛异常——
   FastAPI 会把 body 解析中的任何异常吞掉包装成 HTTPException(400)，异常传不回
   中间件——所以改为：直接用原始 send 发出 413，向应用返回 http.disconnect 让它
   中止处理，并在 wrapped_send 里丢弃应用之后再发的响应（此时 413 已经发出，
   连接上不能再有第二个响应）。

用纯 ASGI 中间件而不是 BaseHTTPMiddleware：后者会把响应包一层 StreamingResponse，
对 /chat 的 SSE 流平添一跳；纯 ASGI 对响应路径零侵入。

已知取舍：若响应已开始（SSE 已发首包）后才发现超限，无法再发 413 只能断流——
但 JSON 接口的 body 解析都在响应开始之前，实际不受影响。上线反向代理后应在
nginx 再配一道 client_max_body_size 作为第一防线。
"""
import json
import logging

from core import config

logger = logging.getLogger("bodylimit")

BODY_MAX_BYTES = config.BODY_MAX_MB * 1024 * 1024


class BodySizeLimitMiddleware:
    def __init__(self, app, max_bytes: int = BODY_MAX_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 防线 1：Content-Length 声明超限，直接拒收
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = None
                if declared is not None and declared > self.max_bytes:
                    logger.warning(
                        "请求体超限（Content-Length=%s > %s）：%s %s",
                        declared, self.max_bytes, scope["method"], scope["path"],
                    )
                    await self._send_413(send)
                    return

        # 防线 2：对实际收到的字节累计计数（防 chunked / header 撒谎）
        received = 0
        response_started = False
        limited = False  # 已因超限发出 413

        async def wrapped_receive():
            nonlocal received, limited
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    limited = True
                    logger.warning(
                        "请求体超限（实际接收 > %s，无有效 Content-Length）：%s %s",
                        self.max_bytes, scope["method"], scope["path"],
                    )
                    if not response_started:
                        await self._send_413(send)
                    return {"type": "http.disconnect"}
            return message

        async def wrapped_send(message):
            nonlocal response_started
            if limited:
                return  # 413 已发出，丢弃应用对"断开"作出的错误响应
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        await self.app(scope, wrapped_receive, wrapped_send)

    async def _send_413(self, send):
        body = json.dumps(
            {"detail": f"请求体过大，最大允许 {config.BODY_MAX_MB}MB"}, ensure_ascii=False
        ).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})
