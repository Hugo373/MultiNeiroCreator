"""tests 全局夹具：在任何被测模块 import 之前准备测试环境变量。

conftest 由 pytest 在收集阶段最先加载，早于测试模块的顶层 import，
所以这里 setdefault 的值能被 core/config.py 读到。
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("RAG_COLLECTION_NAME", "documents_test_ci")

import pytest


@pytest.fixture(autouse=True)
def _isolated_vectorstore(tmp_path, monkeypatch):
    """每个测试用独立的临时 chroma 目录，测试永不触碰真实 chroma_db。

    vectorstore 的连接在首次使用时才建立（见 vectorstore.client_db），
    所以这里在测试开始前 reset 即可让整个 import 链落到 tmp_path。
    """
    from services.rag import vectorstore as vectorstore_module

    monkeypatch.setattr(
        "services.rag.vectorstore.BACKEND_DIR", tmp_path, raising=True
    )
    vectorstore_module.vectorstore.reset()
    yield
    vectorstore_module.vectorstore.reset()


