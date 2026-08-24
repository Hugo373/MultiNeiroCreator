import hashlib
import io
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException, UploadFile

from core import database, migrations
from repositories import document_repo
from services import document_service


def now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture
def document_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_FILE", tmp_path / "documents.db")
    monkeypatch.setattr(document_service.config, "DOCUMENT_STORAGE_DIR", tmp_path / "stored")
    migrations.run_migrations()
    with database.db_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("document-owner@example.com", "hash"),
        )
        user_id = conn.execute("SELECT id FROM users").fetchone()[0]
    return user_id


def create_document(user_id: int, document_id: str = "d" * 32, filename: str = "notes.txt"):
    document, _ = document_repo.create_replacement(
        document_id=document_id,
        user_id=user_id,
        project_id=None,
        filename=filename,
        storage_path=f"/tmp/{document_id}.txt",
        size_bytes=10,
        file_hash="a" * 64,
        created_at=now(),
    )
    return document


def test_replacing_same_filename_hides_old_document(document_db):
    old = create_document(document_db)
    new, old_paths = document_repo.create_replacement(
        document_id="e" * 32,
        user_id=document_db,
        project_id=None,
        filename="notes.txt",
        storage_path="/tmp/new.txt",
        size_bytes=20,
        file_hash="b" * 64,
        created_at=now(),
    )

    assert old_paths == [old["storage_path"]]
    assert new["status"] == "queued"
    assert document_repo.get(old["id"])["status"] == "deleted"
    assert [item["id"] for item in document_repo.list_for_user(document_db)] == [new["id"]]


def test_worker_document_processing_marks_ready(document_db, monkeypatch):
    document = create_document(document_db)
    monkeypatch.setattr(document_service, "add_document", lambda **_kwargs: 4)
    progress: list[tuple[int, str | None]] = []

    # 处理器只关心原文件存在；真实解析在单独的 RAG 测试和 Worker 集成环境验证。
    document_service.Path(document["storage_path"]).parent.mkdir(parents=True, exist_ok=True)
    document_service.Path(document["storage_path"]).touch()
    result = document_service.process_document(
        document["id"],
        lambda value, message: progress.append((value, message)),
        lambda: False,
    )

    stored = document_repo.get(document["id"])
    assert result["chunks_count"] == 4
    assert stored is not None and stored["status"] == "ready"
    assert stored["chunks_count"] == 4
    assert progress[-1][0] == 100


def test_worker_document_processing_marks_failed(document_db, monkeypatch):
    document = create_document(document_db)
    monkeypatch.setattr(
        document_service, "add_document", lambda **_kwargs: (_ for _ in ()).throw(ValueError("bad file"))
    )
    document_service.Path(document["storage_path"]).parent.mkdir(parents=True, exist_ok=True)
    document_service.Path(document["storage_path"]).touch()

    with pytest.raises(ValueError, match="bad file"):
        document_service.process_document(document["id"], lambda *_args: None, lambda: False)

    stored = document_repo.get(document["id"])
    assert stored is not None
    assert stored["status"] == "failed"
    assert stored["error"] == "bad file"


@pytest.mark.asyncio
async def test_upload_saves_original_and_enqueues_job(document_db):
    upload = UploadFile(filename="folder/notes.txt", file=io.BytesIO("原始内容".encode()))

    result = await document_service.enqueue_upload(upload, document_db, None, len("原始内容".encode()))
    document = result["document"]
    job = result["job"]

    assert result["status"] == "accepted"
    assert document["status"] == "queued"
    assert document["job_id"] == job["id"]
    assert job["type"] == "document_ingest"
    assert job["payload"] == {"document_id": document["id"]}
    assert document["file_hash"] == hashlib.sha256("原始内容".encode()).hexdigest()
    with open(document["storage_path"], encoding="utf-8") as stored_file:
        assert stored_file.read() == "原始内容"


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_extension(document_db):
    upload = UploadFile(filename="malware.exe", file=io.BytesIO(b"not a supported document"))

    with pytest.raises(HTTPException, match="仅支持"):
        await document_service.enqueue_upload(upload, document_db, None, 24)
