# MultiNeiroCreator

AI 创作工作台：流式对话助手 + RAG 文档问答 + 可视化工作流画布。

- **对话助手（Neyria）**：SSE 流式输出，ReAct 多轮工具循环（计算器 / 时间 / 联网搜索），支持附件。
- **RAG**：BGE-M3 embedding（SiliconFlow）+ ChromaDB，按距离阈值过滤，无命中时自动后备联网搜索，回答附带引用来源。
- **文档索引**：上传 PDF / docx / txt / md / json，异步任务队列处理（SQLite 租约 + 心跳 + 取消 + 重试），进度可查。
- **工作流画布**：节点编排、连线防环、撤销重做、小地图，按项目隔离存储。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI、SSE、SQLite（WAL + 版本化迁移）、ChromaDB、Redis（限流/验证码）、uv |
| 前端 | Vue 3 + TypeScript + Vite、Pinia、Element Plus、Vitest |
| 模型 | 智谱 GLM-4-Flash（对话）、SiliconFlow BGE-M3（embedding） |

## 目录结构

```
backend/
  agents/          Neyria 定义与工具（注册表统一管理 schema 与实现）
  services/        业务层：chat_orchestrator / context_builder / tool_executor / rag/ / job_service
  workers/         后台任务 worker（租约、心跳、取消）
  repositories/    SQL 层（唯一落库点）
  core/            配置、安全、限流、迁移、日志
  tests/           pytest，129+ 用例
frontend/
  components/      assistant / workflow / creative / task / project / settings
  stores/          Pinia：chat / project / workflow / loading / user
  serve/           API 客户端（SSE 解析带逐行容错）
```

## 快速开始

前置：Python 3.12+（[uv](https://docs.astral.sh/uv/)）、Node 20+（pnpm）、Redis。

### 后端

```bash
cd backend
uv sync --all-groups
cp .env.example .env        # 填入 SECRET_KEY、API_KEY、SILICONFLOW_API_KEY、SMTP 配置
uv run uvicorn main:app --port 8000 --reload
```

Linux/macOS 可用一键脚本（含 Redis 检查）：`./dev.sh`。

### 后台 worker（文档索引）

```bash
cd backend
uv run python -m workers.job_worker
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev                    # http://localhost:5173
```

## Docker

```bash
cd backend
docker compose up --build   # api + worker + redis
```

## 环境变量

所有配置集中在 `backend/core/config.py`，均可用环境变量覆盖。常用项：

| 变量 | 说明 | 默认 |
|---|---|---|
| `SECRET_KEY` | JWT 签名密钥，**必填**，缺失拒绝启动 | — |
| `API_KEY` | 智谱 API Key（对话模型） | — |
| `SILICONFLOW_API_KEY` | SiliconFlow API Key（embedding） | — |
| `EMBEDDING_MODEL` | embedding 模型 | `BAAI/bge-m3` |
| `RAG_COLLECTION_NAME` | Chroma collection 名 | `documents_siliconflow_bge_m3` |
| `RAG_DISTANCE_THRESHOLD` | 检索距离阈值，超过视为无命中 | `1.10` |
| `REDIS_URL` | Redis 连接 | `redis://localhost:6379/0` |
| `CORS_ORIGINS` | 允许的前端来源 | `http://localhost:5173,...` |
| `MAIL_HOST` / `MAIL_USER` / `MAIL_PASS` | SMTP（注册验证码，QQ 邮箱 465/SSL） | `smtp.qq.com` |

## 开发

```bash
# 后端：lint + 类型 + 测试
cd backend
uv run ruff check .
uv run mypy
uv run pytest -q            # 测试使用独立临时 chroma 目录，可并行

# 前端
cd frontend
pnpm lint && pnpm test && pnpm build
```

推送与 PR 会触发 GitHub Actions：后端（ruff + mypy + pytest，含 Redis service）与前端（ESLint + Prettier + Vitest + build）。

## 测试

后端 `uv run pytest -q`；前端 `pnpm test`（Vitest）。测试环境自带隔离的临时向量库，不读写真实 `chroma_db/`。
