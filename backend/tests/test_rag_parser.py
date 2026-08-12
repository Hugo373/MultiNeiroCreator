"""RAG 文本切分 chunk_text 的边界测试（F2 第一批清单）。

G4（overlap/切分策略优化）动手前，先用测试钉住当前行为作为基线。
"""

import pytest

from services.rag.parser import chunk_text

# ---------- 参数边界 ----------


def test_invalid_chunk_size_rejected():
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=-1)


def test_negative_overlap_rejected():
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_overlap=-1)


def test_overlap_must_be_less_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=10, chunk_overlap=10)
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=10, chunk_overlap=15)


# ---------- 切分行为 ----------


def test_empty_text_returns_empty_list():
    assert chunk_text("") == []


def test_whitespace_only_returns_empty_list():
    assert chunk_text("   \n\t  ") == []


def test_short_text_single_chunk():
    assert chunk_text("hello", chunk_size=500) == ["hello"]


def test_exact_boundary_no_empty_tail():
    # 文本长度恰为 chunk_size 时只产出一个 chunk，不应出现空尾块
    text = "a" * 10
    assert chunk_text(text, chunk_size=10, chunk_overlap=3) == [text]


def test_overlap_produces_shared_prefix():
    # chunk_size=10, overlap=3 → 步长 7：第二块的前 3 字符 = 第一块的后 3 字符
    text = "0123456789ABCDEFGHIJ"
    chunks = chunk_text(text, chunk_size=10, chunk_overlap=3)
    assert chunks[0] == "0123456789"
    assert chunks[1].startswith(chunks[0][-3:])


def test_all_content_covered():
    # 无 overlap 时各块拼接应还原原文（无空白被 strip 的场景）
    text = "abcdefghij" * 5
    chunks = chunk_text(text, chunk_size=7, chunk_overlap=0)
    assert "".join(chunks) == text


def test_chunks_never_exceed_chunk_size():
    text = "x" * 1000
    for chunk in chunk_text(text, chunk_size=64, chunk_overlap=16):
        assert len(chunk) <= 64
