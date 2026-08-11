from datetime import datetime, timedelta

import bcrypt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from core.config import ACCESS_TOKEN_EXPIRE_DAYS, ALGORITHM, SECRET_KEY
from core.logging_config import user_id_var


bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    pw = password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "username": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        # 鉴权唯一入口：在这里把 user_id 写进请求作域域 ContextVar，本请求后续所有日志自动携带
        user_id_var.set(str(user_id))
        return {"id": user_id, "username": payload.get("username")}
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="token无效或已过期") from exc
