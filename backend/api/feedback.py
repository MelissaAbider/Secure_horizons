"""Human feedback and audit-history API. This API records labels; it never retrains or promotes a model."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.feedback import AlertFeedbackView, FeedbackLedger, FeedbackRequest, LedgerEvent, feedback_ledger

router = APIRouter(tags=["ml-feedback"])


def get_ledger() -> FeedbackLedger:
    return feedback_ledger


@router.get("/feedback", response_model=list[AlertFeedbackView])
def feedback_history(alert_id: str | None = Query(default=None)):
    return get_ledger().views(alert_id)


@router.get("/feedback/integrity")
def feedback_integrity():
    valid, errors = get_ledger().verify()
    return {"valid": valid, "errors": errors, "training_side_effect": False}


@router.post("/alerts/{alert_id}/feedback", response_model=LedgerEvent)
def submit_feedback(alert_id: str, request: FeedbackRequest):
    try:
        return get_ledger().review(alert_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail="Alert observation not found") from None


@router.get("/feedback/export")
def export_feedback_dataset():
    rows = get_ledger().export_training_rows()
    return {"schema_version": 1, "purpose": "offline_challenger_training_only", "active_model_changed": False,
            "rows": rows, "count": len(rows)}
