"""Import every model here.

Alembic can only generate a migration for models it has imported, and
SQLAlchemy resolves relationships by name at configuration time. Importing
them all in one place guarantees both.
"""
from app.models.audit import AuditEvent
from app.models.dose import DoseEvent
from app.models.medication import DoseSchedule, Medication
from app.models.notification import Notification
from app.models.safety import SafetyFinding, finding_medications
from app.models.user import ConsentGrant, User

__all__ = [
    "AuditEvent",
    "ConsentGrant",
    "DoseEvent",
    "DoseSchedule",
    "Medication",
    "Notification",
    "SafetyFinding",
    "User",
    "finding_medications",
]
