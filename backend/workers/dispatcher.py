import logging
from collections.abc import Callable
from typing import Any

from services.document_service import process_document

logger = logging.getLogger("job_worker")


class JobCancelled(Exception):
    """任务在安全检查点发现用户取消请求。"""


JobContext = Callable[[int, str | None], None]


def handle_document_index(
    job: dict[str, Any],
    update_progress: JobContext,
    is_cancel_requested: Callable[[], bool],
) -> dict[str, Any]:
    try:
        return process_document(
            document_id=job["payload"]["document_id"],
            update_progress=update_progress,
            is_cancel_requested=is_cancel_requested,
        )
    except InterruptedError as exc:
        raise JobCancelled(str(exc)) from exc


JOB_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "document_ingest": handle_document_index,
    "document_reindex": handle_document_index,
}
