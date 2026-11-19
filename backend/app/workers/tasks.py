"""Scheduled jobs.

Each task opens its own database session and always closes it. A worker
process is long-lived, so a leaked session here would accumulate for days.
"""
import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.dose import DoseEvent
from app.models.enums import DoseStatus, MedicationStatus, Severity
from app.models.medication import Medication
from app.models.user import User
from app.services import dose_scheduler
from app.services.recall_monitor import RecallMonitor
from app.services.safety_engine import SafetyEngine
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.check_recalls")
def check_recalls(days: int = 30) -> dict:
    """Poll openFDA and create findings for affected patients.

    This is the task behind the demo line: nobody opened the application, and
    a caregiver was still told their patient's medication was recalled.
    """
    with SessionLocal() as db:
        monitor = RecallMonitor(db)
        created = monitor.check_recent(days=days)
        db.commit()
        summary = {
            "findings_created": len(created),
            "severe": sum(1 for f in created if f.severity == Severity.SEVERE),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    logger.info("check_recalls: %s", summary)
    return summary


@celery_app.task(name="app.workers.tasks.simulate_recall")
def simulate_recall(drug_name: str) -> dict:
    """Demo helper: process real historical recalls for one drug on cue."""
    with SessionLocal() as db:
        created = RecallMonitor(db).simulate_for_drug(drug_name)
        db.commit()
        return {"drug": drug_name, "findings_created": len(created)}


@celery_app.task(name="app.workers.tasks.refresh_dose_statuses")
def refresh_dose_statuses() -> dict:
    """Move doses from DUE to MISSED once their grace period has elapsed.

    Without this, a dose only changes status when someone opens the app - so a
    missed dose would be invisible precisely when nobody is looking, which is
    exactly when it matters.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=2)

    with SessionLocal() as db:
        stmt = select(DoseEvent).where(
            DoseEvent.scheduled_for >= window_start,
            DoseEvent.scheduled_for <= now,
            DoseEvent.status.in_([DoseStatus.SCHEDULED, DoseStatus.DUE]),
        )
        events = list(db.execute(stmt).scalars().all())
        changed = dose_scheduler.refresh_statuses(db, events, now=now)
        db.commit()

    logger.info("refresh_dose_statuses: %d of %d updated", changed, len(events))
    return {"examined": len(events), "updated": changed}


@celery_app.task(name="app.workers.tasks.generate_upcoming_doses")
def generate_upcoming_doses(days: int = 7) -> dict:
    """Keep a rolling window of expected doses in place.

    Idempotent, so running it on a timer never produces duplicates.
    """
    created_total = 0
    with SessionLocal() as db:
        patient_ids = db.execute(
            select(Medication.patient_id)
            .where(Medication.status == MedicationStatus.ACTIVE)
            .distinct()
        ).scalars().all()

        for patient_id in patient_ids:
            created = dose_scheduler.generate_dose_events(
                db, patient_id=patient_id, start=date.today(), days=days
            )
            created_total += len(created)
        db.commit()

    return {"patients": len(patient_ids), "doses_created": created_total}


@celery_app.task(name="app.workers.tasks.evaluate_all_patients")
def evaluate_all_patients() -> dict:
    """Re-run the safety engine for every patient."""
    created_total = 0
    with SessionLocal() as db:
        patient_ids = db.execute(
            select(Medication.patient_id)
            .where(Medication.status == MedicationStatus.ACTIVE)
            .distinct()
        ).scalars().all()

        engine = SafetyEngine(db)
        for patient_id in patient_ids:
            created_total += len(engine.evaluate_patient(patient_id).created)
        db.commit()

    return {"patients": len(patient_ids), "findings_created": created_total}
