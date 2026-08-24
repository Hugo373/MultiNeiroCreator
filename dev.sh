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

# 先让 FastAPI 完成迁移，再启动 Worker。否则 Worker 抢先访问新库时会因 documents
# 尚未建表直接退出，开发者会误以为任务队列坏了。
echo "[dev] 启动后端并等待数据库迁移完成"
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload &
server_pid=$!
worker_pid=""

cleanup() {
  if [ -n "$worker_pid" ]; then kill "$worker_pid" 2>/dev/null || true; fi
  kill "$server_pid" 2>/dev/null || true
  if [ -n "$worker_pid" ]; then wait "$worker_pid" 2>/dev/null || true; fi
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo "[dev] 后端启动失败" >&2
    exit 1
  fi
  sleep 0.5
done
if ! curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "[dev] 等待后端健康检查超时" >&2
  exit 1
fi

echo "[dev] 数据库迁移完成，启动 E3 后台 Worker"
uv run python -m workers.job_worker &
worker_pid=$!

wait "$server_pid"
