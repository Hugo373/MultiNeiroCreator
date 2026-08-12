# MultiNeiroCreator

[![CI](https://github.com/Cyrivea/MultiNeiroCreator/actions/workflows/ci.yml/badge.svg)](https://github.com/Cyrivea/MultiNeiroCreator/actions/workflows/ci.yml)

AI 多智能体创作工作台：注册登录 + 流式对话（SSE）+ RAG 文档问答 + 项目工作区。

> 完整的架构说明、API 文档与部署文档在建（见 `unsolved.md` H2）。本 README 先提供最小可复现指引。

## 技术栈

- **后端**：Python 3.12 / FastAPI / SQLite / Redis / ChromaDB，依赖管理 [uv](https://docs.astral.sh/uv/)
- **前端**：Vue 3 / TypeScript / Vite / Pinia，包管理 pnpm

## 快速启动（开发环境）

```bash
# 后端（需要 backend/.env，至少包含 SECRET_KEY；LLM/embedding 需 API_KEY/EMBEDDING_API_KEY）
./dev.sh                 # 自动检查/拉起 Redis + 启动 uvicorn --reload

# 前端
cd frontend
pnpm install
pnpm dev
```

## 质量门禁（与 CI 一致）

```bash
# 后端（backend/ 目录）
uv sync --all-groups     # 安装含 dev 组的全部依赖
uv run ruff check .      # lint
uv run mypy              # 类型检查（core/schemas/services/rag）
uv run pytest            # 84 个用例（Redis 不在时相关用例自动跳过）

# 前端（frontend/ 目录）
pnpm lint                # ESLint
pnpm format:check        # Prettier
pnpm test                # Vitest（30 个用例）
pnpm build               # vue-tsc + vite
```
