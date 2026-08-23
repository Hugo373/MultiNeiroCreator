# MultiNeiroCreator

[![CI](https://github.com/Cyrivea/MultiNeiroCreator/actions/workflows/ci.yml/badge.svg)](https://github.com/Cyrivea/MultiNeiroCreator/actions/workflows/ci.yml)

AI 多智能体创作工作台：注册登录 + 流式对话（SSE）+ RAG 文档问答 + 项目工作区。

> 完整的架构说明见 `architecture.md`；API/部署文档与量化指标仍在补充（见 `unsolved.md` H2/H3）。本 README 提供最小可复现指引。

## 技术栈

- **后端**：Python 3.12 / FastAPI / SQLite / Redis / ChromaDB，依赖管理 [uv](https://docs.astral.sh/uv/)
- **前端**：Vue 3 / TypeScript / Vite / Pinia，包管理 pnpm

## 快速启动（开发环境）

```bash
# 后端（需要 backend/.env，至少包含 SECRET_KEY；聊天用 API_KEY，RAG 使用 SiliconFlow 的 SILICONFLOW_API_KEY）
./dev.sh                 # 自动检查/拉起 Redis + 启动 uvicorn --reload

# 前端
cd frontend
pnpm install
pnpm dev
```

```env
# 聊天：智谱
API_KEY=...
# RAG：硅基流动免费版 BAAI/bge-m3
SILICONFLOW_API_KEY=...
EMBEDDING_MODEL=BAAI/bge-m3
```


```bash
# 后端（backend/ 目录）
uv sync --all-groups     # 安装含 dev 组的全部依赖
uv run ruff check .      # lint
uv run mypy              # 类型检查（core/schemas/services/rag）
uv run pytest            # 113 passed，Redis 不在时相关用例自动跳过

# 前端（frontend/ 目录）
pnpm lint                # ESLint
pnpm format:check        # Prettier
pnpm test                # Vitest（30 个用例）
pnpm build               # vue-tsc + vite
```
