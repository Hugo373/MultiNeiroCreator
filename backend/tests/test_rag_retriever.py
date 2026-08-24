"""RAG 距离阈值测试：无相关命中时才能进入联网后备。"""

from services.rag.retriever import _build_chunk_metadatas, _filter_by_distance, retrieve_document_hits


def test_distance_filter_keeps_relevant_chunks() -> None:
    documents = ["近命中", "远命中", "第二个近命中"]
    distances = [0.68, 1.42, 1.09]

    assert _filter_by_distance(documents, distances, 1.10) == ["近命中", "第二个近命中"]


def test_distance_filter_returns_empty_when_all_chunks_are_irrelevant() -> None:
    assert _filter_by_distance(["无关资料"], [1.25], 1.10) == []


def test_distance_filter_does_not_fake_hit_without_distances() -> None:
    assert _filter_by_distance(["资料"], None, 1.10) == []


def test_indexed_chunks_keep_document_identity_and_citation_metadata() -> None:
    metadata = _build_chunk_metadatas(
        "guide.md",
        3,
        user_id=7,
        project_id=11,
        document_id="a" * 32,
    )

    assert metadata[1]["document_id"] == "a" * 32
    assert metadata[1]["chunk_index"] == 1
    assert metadata[1]["chunk_count"] == 3


def test_retrieve_hits_preserve_source_and_distance(monkeypatch) -> None:
    class FakeStore:
        def count(self):
            return 1

        def query(self, **_kwargs):
            return {
                "documents": [["相关片段"]],
                "metadatas": [
                    [{"source": "guide.md", "document_id": "a" * 32, "chunk_index": 2, "chunk_count": 4}]
                ],
                "distances": [[0.42]],
            }

    monkeypatch.setattr("services.rag.retriever.vectorstore", FakeStore())
    hits = retrieve_document_hits([0.1], user_id=7, project_id=11, max_distance=1.1)

    assert hits == [
        {
            "content": "相关片段",
            "source": "guide.md",
            "document_id": "a" * 32,
            "chunk_index": 2,
            "chunk_count": 4,
            "distance": 0.42,
        }
    ]
