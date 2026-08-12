"""core/security.py 的单元测试（F2 第一批清单：密码哈希与校验、JWT 创建/过期/错误签名）。

不 mock bcrypt/jose：这两个库本身就是被测对象的一部分，且都是纯本地计算，不耗额度。
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from core.config import ALGORITHM, SECRET_KEY
from core.security import create_token, decode_token, hash_password, verify_password

# ---------- 密码哈希与校验 ----------


def test_hash_and_verify_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong password", h)


def test_hash_is_salted():
    # 同一密码两次哈希应不同（bcrypt 每次生成随机盐）
    assert hash_password("samepassword") != hash_password("samepassword")


def test_verify_malformed_hash_returns_false():
    # 数据库脏数据/迁移残留不应抛异常，而是安静返回 False
    assert not verify_password("whatever", "not-a-bcrypt-hash")
    assert not verify_password("whatever", "")


def test_bcrypt_72_byte_truncation_documented():
    # bcrypt 只看前 72 字节，hash_password 显式截断。
    # 这是已知行为（注册侧 schema 已拒绝 >72 字节密码），测试在此固化语义：
    # 若未来换算法（如 argon2），此测试提醒重新评估截断逻辑
    long_pw = "a" * 80
    h = hash_password(long_pw)
    assert verify_password("a" * 72, h)  # 前 72 字节相同 → 通过


# ---------- JWT ----------


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_create_and_decode_token():
    token = create_token(user_id=7, username="alice@example.com")
    user = decode_token(_creds(token))
    assert user == {"id": 7, "username": "alice@example.com"}


def test_expired_token_rejected():
    expired = jwt.encode(
        {"sub": "7", "username": "alice", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_token(_creds(expired))
    assert exc_info.value.status_code == 401


def test_wrong_signature_rejected():
    forged = jwt.encode(
        {"sub": "7", "username": "alice", "exp": datetime.now(UTC) + timedelta(days=1)},
        "attacker-key",
        algorithm=ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_token(_creds(forged))
    assert exc_info.value.status_code == 401


def test_garbage_token_rejected():
    with pytest.raises(HTTPException) as exc_info:
        decode_token(_creds("not.a.jwt"))
    assert exc_info.value.status_code == 401
