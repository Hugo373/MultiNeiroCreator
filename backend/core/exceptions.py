"""业务异常与全局异常处理器。

分三层兜底（在 main.py 注册）：
- AppError：业务层主动抛出的可预期错误，带状态码和用户可读信息；
- RequestValidationError：入参校验失败，日志只记字段路径不记字段值（防密码等入日志）；
- Exception：未预期错误。响应只含通用文案 + request_id（供用户报障），
  完整 traceback 只进服务端日志——修复"堆栈原文吐给前端"的信息泄漏。

注意：Exception 兜底 handler 挂在 ServerErrorMiddleware 上，它在用户中间件栈
外层，生成的响应不会经过 RequestContextMiddleware 的 wrapped_send，所以
X-Request-ID 响应头要在这里自己带上。
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.logging_config import request_id_var

logger = logging.getLogger("exceptions")


class AppError(Exception):
    """业务可预期错误：service 层抛出，全局 handler 统一转 JSON 响应。"""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.info(
            "业务异常: %s", exc.detail,
            extra={"evt": "app_error", "status": exc.status_code, "path": request.url.path},
        )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # 只记字段路径（如 body.password），不记字段值
        fields = [".".join(str(part) for part in err.get("loc", [])) for err in exc.errors()]
        logger.info(
            "入参校验失败: %s", fields,
            extra={"evt": "validation_error", "path": request.url.path, "fields": fields},
        )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request_id_var.get()
        logger.error(
            "未处理异常: %s: %s", type(exc).__name__, exc,
            exc_info=exc,
            extra={"evt": "unhandled_error", "path": request.url.path,
                   "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误，请稍后重试", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )
