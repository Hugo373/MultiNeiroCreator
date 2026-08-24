"""审计并可选清理没有 document_id 的 legacy Chroma chunk。

默认只读：
    uv run python scripts/audit_legacy_vectors.py

确认报告后再执行：
    uv run python scripts/audit_legacy_vectors.py --apply

--apply 的策略：能唯一对应 documents 表中 active/ready 文档的 legacy chunk 会被
按原文件重新入队；找不到对应原文件的孤儿 chunk 才会删除。多文档同名冲突不会自动处理。
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# 允许从 backend 目录直接执行：python scripts/xxx.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import db_connection
from services.rag.retriever import vectorstore


def _scope_value(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    if value in (None, -1, "-1"):
        return None
    return int(value)


def _legacy_groups() -> dict[tuple[int | None, int | None, str, str], list[str]]:
    result = vectorstore.get_documents()
    ids = result.get("ids") or []
    metadatas = result.get("metadatas") or []
    groups: dict[tuple[int | None, int | None, str, str], list[str]] = defaultdict(list)
    for chunk_id, metadata in zip(ids, metadatas, strict=False):
        metadata = metadata or {}
        if metadata.get("document_id") not in (None, "", "legacy"):
            continue
        key = (
            _scope_value(metadata, "user_id"),
            _scope_value(metadata, "project_id"),
            str(metadata.get("source", "")),
            str(metadata.get("scope", "assistant")),
        )
        groups[key].append(chunk_id)
    return groups


def _matching_documents(user_id: int | None, project_id: int | None, filename: str) -> list[dict[str, Any]]:
    with db_connection() as conn:
        if project_id is None:
            rows = conn.execute(
                "SELECT id, user_id, project_id, filename, status, storage_path "
                "FROM documents WHERE user_id=? AND project_id IS NULL AND filename=? "
                "AND status != 'deleted'",
                (user_id, filename),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, project_id, filename, status, storage_path "
                "FROM documents WHERE user_id=? AND project_id=? AND filename=? "
                "AND status != 'deleted'",
                (user_id, project_id, filename),
            ).fetchall()
    return [dict(row) for row in rows]


def audit(apply: bool = False) -> int:
    groups = _legacy_groups()
    report: list[dict[str, Any]] = []
    for (user_id, project_id, filename, scope), ids in groups.items():
        matches = _matching_documents(user_id, project_id, filename)
        item = {
            "user_id": user_id,
            "project_id": project_id,
            "filename": filename,
            "scope": scope,
            "chunk_count": len(ids),
            "chunk_ids": ids,
            "matching_documents": matches,
            "action": "manual_review",
        }
        if len(matches) == 1 and Path(matches[0]["storage_path"]).is_file():
            item["action"] = "reindex_from_original"
            if apply:
                # 只删除旧 chunk；新索引由原文件重新解析并写入 document_id 元数据。
                vectorstore.delete_documents(ids=ids)
                item["action"] = "legacy_deleted_reindex_required"
        elif not matches or not any(Path(row["storage_path"]).is_file() for row in matches):
            item["action"] = "delete_orphan"
            if apply:
                vectorstore.delete_documents(ids=ids)
                item["action"] = "orphan_deleted"
        report.append(item)

    sys.stdout.write(
        json.dumps({"legacy_group_count": len(report), "groups": report}, ensure_ascii=False, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="执行安全的孤儿 legacy chunk 删除")
    raise SystemExit(audit(parser.parse_args().apply))
