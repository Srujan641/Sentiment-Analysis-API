"""GET /api/v1/monitoring/drift — live prediction window vs. training reference."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_drift

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/drift")
async def drift_report(drift=Depends(get_drift)):
    """PSI on input length, confidence and label mix over the last `DRIFT_WINDOW` predictions."""
    if drift is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Drift monitor is not running")
    return drift.report()
