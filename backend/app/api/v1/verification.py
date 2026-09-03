"""FastAPI Endpoints for Fact-Checking and Verification Agent."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_event_repo
from app.repositories.event_repository import EventRepository
from app.schemas.verification import (
    ClaimVerificationOutput,
    EventVerificationResponse,
    VerifyClaimRequest,
    VerifyEventRequest,
)
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/verification", tags=["Verification"])


@router.post("/verify-claim", response_model=ClaimVerificationOutput)
async def verify_claim(request: VerifyClaimRequest):
    """Verify an isolated user-submitted or atomic claim."""
    async with VerificationService() as service:
        return await service.verify_standalone_claim(
            claim_text=request.claim,
            context=request.context,
        )


@router.post("/verify-event/{event_id}", response_model=EventVerificationResponse)
async def verify_event_claims(
    event_id: UUID,
    request: VerifyEventRequest = VerifyEventRequest(),
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Extract and verify all checkable claims within an event cluster."""
    service = VerificationService(event_repo.db, event_repo)
    try:
        return await service.verify_event_by_id(
            event_id=event_id,
            force_recheck=request.force_recheck,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/event/{event_id}", response_model=EventVerificationResponse)
async def get_event_verification(
    event_id: UUID,
    event_repo: EventRepository = Depends(get_event_repo),
):
    """Retrieve verified claims and full evidence traceability for an event."""
    service = VerificationService(event_repo.db, event_repo)
    try:
        return await service.verify_event_by_id(
            event_id=event_id,
            force_recheck=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
