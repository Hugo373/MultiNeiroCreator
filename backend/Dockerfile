# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 先只拷贝依赖清单，利用层缓存：依赖不变时跳过安装
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

FROM python:3.12-slim
# 非 root 运行；预创建数据目录并赋权（SQLite 与文档落盘在 /app/data）
RUN useradd --create-home appuser \
    && mkdir -p /app/data /app/chroma_db \
    && chown -R appuser:appuser /app/data /app/chroma_db
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser . .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

# SECRET_KEY 必须由环境注入，缺失时服务自行拒绝启动（core/config.py）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
