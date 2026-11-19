"""Attach plain-language explanations to findings that do not have one."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import FindingStatus
from app.models.safety import SafetyFinding
from app.services.ai_explainer import MODEL, AIExplainer

logger = logging.getLogger(__name__)


def explain_pending(db: Session, limit: int = 25, explainer: AIExplainer | None = None) -> dict:
    """Explain findings that are still waiting for one.

    Runs after the engine, never before. A finding without an explanation is a
    complete, displayable finding - this only makes it friendlier.
    """
    explainer = explainer or AIExplainer()

    stmt = (
        select(SafetyFinding)
        .where(
            SafetyFinding.ai_explanation.is_(None),
            SafetyFinding.status != FindingStatus.RESOLVED,
        )
        .order_by(SafetyFinding.detected_at.desc())
        .limit(limit)
    )
    findings = list(db.execute(stmt).scalars().all())

    counts = {"ok": 0, "rejected": 0, "unavailable": 0, "disabled": 0}

    for finding in findings:
        names = [m.name_entered for m in finding.medications][:2]
        result = explainer.explain(
            title=finding.title,
            detail=finding.detail,
            source_name=finding.source_name,
            level=(finding.evidence or {}).get("level"),
            drug_a=names[0] if names else None,
            drug_b=names[1] if len(names) > 1 else None,
        )
        counts[result.status] = counts.get(result.status, 0) + 1

        if result.usable:
            finding.ai_explanation = result.text
            finding.ai_model = MODEL
            finding.ai_generated_at = datetime.now(timezone.utc)

    db.flush()
    logger.info("explain_pending: %s", counts)
    return {"examined": len(findings), **counts}
