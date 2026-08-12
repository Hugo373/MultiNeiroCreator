#!/usr/bin/env bash
# 开发环境一键启动（F8）：先确保 Redis 存活，再拉起后端。
# 用法：./dev.sh          启动后端（含 Redis 检查）
#       ./dev.sh redis    只做 Redis 检查/拉起
set -euo pipefail

cd "$(dirname "$0")"

ensure_redis() {
  if redis-cli ping >/dev/null 2>&1; then
    echo "[dev] Redis 已在运行"
    return
  fi
  echo "[dev] Redis 未运行，正在拉起……"
  redis-server --daemonize yes
  # 最多等 5 秒确认起来了，起不来就把原因打出来（后端 fail-fast 依赖它）
  for _ in $(seq 1 10); do
    if redis-cli ping >/dev/null 2>&1; then
      echo "[dev] Redis 已就绪"
      return
    fi
    sleep 0.5
  done
  echo "[dev] Redis 拉起失败，请手动排查：redis-server（前台模式看报错）" >&2
  exit 1
}

ensure_redis
[ "${1:-}" = "redis" ] && exit 0

cd backend
exec uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
