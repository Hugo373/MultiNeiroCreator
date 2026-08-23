"""系统提示词的知识来源路由契约测试。"""

from agents.neyria import build_system_prompt


def test_private_knowledge_context_forbids_web_search() -> None:
    prompt = build_system_prompt("", "区块链技术具有去中心化和不可篡改的特点。")

    assert "知识库检索结果" in prompt
    assert "不得调用 search_web" in prompt
    assert "不要声称“无法访问用户文件/设备”" in prompt
    assert "<knowledge_base_context>" in prompt


def test_empty_knowledge_context_explains_retrieval_miss() -> None:
    prompt = build_system_prompt("", "")

    assert "没有检索到足够相关的知识库内容" in prompt
    assert "当前项目的私有 RAG 知识库" not in prompt


def test_web_search_is_reserved_for_external_current_information() -> None:
    prompt = build_system_prompt("", "检索到的内部资料")

    assert "实时信息、新闻、天气、最新事件" in prompt
    assert "知识库问题不适用这条规则" in prompt
