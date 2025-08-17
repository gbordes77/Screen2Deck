from typing import Any, Optional
_jobs: dict[str, Any] = {}
async def set_job(job_id: str, value: Any): _jobs[job_id] = value
async def get_job(job_id: str) -> Optional[Any]: return _jobs.get(job_id)