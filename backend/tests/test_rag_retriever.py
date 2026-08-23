"""RAG 距离阈值测试：无相关命中时才能进入联网后备。"""

from services.rag.retriever import _filter_by_distance


def test_distance_filter_keeps_relevant_chunks() -> None:
    documents = ["近命中", "远命中", "第二个近命中"]
    distances = [0.68, 1.42, 1.09]

    assert _filter_by_distance(documents, distances, 1.10) == ["近命中", "第二个近命中"]


def test_distance_filter_returns_empty_when_all_chunks_are_irrelevant() -> None:
    assert _filter_by_distance(["无关资料"], [1.25], 1.10) == []


def test_distance_filter_does_not_fake_hit_without_distances() -> None:
    assert _filter_by_distance(["资料"], None, 1.10) == []


def test_distance_filter_can_be_disabled_for_maintenance_queries() -> None:
    documents = ["资料一", "资料二"]

    assert _filter_by_distance(documents, None, None) == documents
