"""Every fixed set of values used in the database.

Why enums instead of plain strings: the database itself rejects an invalid
value. A typo like "SEVER" fails at write time rather than silently creating a
severity nobody handles. These also become the allowed values in the API docs.
"""
import enum


class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    CAREGIVER = "CAREGIVER"
    ADMIN = "ADMIN"


class ConsentStatus(str, enum.Enum):
    """A caregiver may only see a patient through an ACTIVE grant."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class MedicationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"


class Frequency(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class DoseStatus(str, enum.Enum):
    """The dose state machine.

    SCHEDULED -> DUE -> TAKEN
                     -> MISSED   (grace period elapsed with no confirmation)
                     -> SKIPPED  (patient deliberately skipped it)
    """
    SCHEDULED = "SCHEDULED"
    DUE = "DUE"
    TAKEN = "TAKEN"
    MISSED = "MISSED"
    SKIPPED = "SKIPPED"


class FindingType(str, enum.Enum):
    INTERACTION = "INTERACTION"
    RECALL = "RECALL"
    DUPLICATE_THERAPY = "DUPLICATE_THERAPY"


class Severity(str, enum.Enum):
    """Drives who gets told. See NotificationService routing rules."""
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class FindingStatus(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class RecallMatch(str, enum.Enum):
    """Tiered recall matching - our defence against false alarms.

    CONFIRMED: the recall names the exact product (NDC) the patient holds.
    POSSIBLE:  same drug, manufacturer unknown. The patient is asked to check
               the label rather than being told they are affected.
    """
    CONFIRMED = "CONFIRMED"
    POSSIBLE = "POSSIBLE"


class NotificationChannel(str, enum.Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"


class NotificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
