from fastapi import APIRouter, Depends, Query

from core.deps import verify_token
from schemas.job import JobResponse
from services.job_service import cancel_job, get_job, list_jobs, retry_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
def list_jobs_route(
    project_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(verify_token),
):
    return list_jobs(user["id"], project_id, limit)


@router.get("/{job_id}", response_model=JobResponse)
def get_job_route(job_id: str, user=Depends(verify_token)):
    return get_job(user["id"], job_id)


@router.post("/{job_id}/cancel", response_model=JobResponse)
def cancel_job_route(job_id: str, user=Depends(verify_token)):
    return cancel_job(user["id"], job_id)


@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job_route(job_id: str, user=Depends(verify_token)):
    return retry_job(user["id"], job_id)
