from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

from core.security import bearer_scheme, decode_token


# 必须是 async 依赖：同步依赖会被 FastAPI 丢进线程池，contextvars 以副本形式传入线程，
# 函数里写的 user_id_var 传不回请求主上下文，access log 就丢了 user_id。
# async 依赖在请求同一个 task 里执行，set 对后续及外层中间件可见。JWT 解码是微秒级
# CPU 操作，放事件循环无阻塞风险。
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    return decode_token(credentials)
