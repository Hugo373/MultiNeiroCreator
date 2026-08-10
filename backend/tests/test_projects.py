import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from services import project_service


def test_get_project_returns_owner_project(tmp_path, monkeypatch):
    monkeypatch.setattr(project_service, "DB_FILE", tmp_path / "projects.db")

    created = project_service.create_project(42, "Alpha", "Folder Alpha")

    loaded = project_service.get_project(42, created["id"])
    assert loaded is not None
    assert loaded["id"] == created["id"]
    assert loaded["name"] == "Alpha"
    assert loaded["project_path"] == "Folder Alpha"

    assert project_service.get_project(43, created["id"]) is None
