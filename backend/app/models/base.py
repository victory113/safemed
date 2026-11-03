"""Shared building blocks for every model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def uuid_pk() -> Mapped[uuid.UUID]:
    """A UUID primary key.

    Why UUIDs and not 1, 2, 3: sequential ids leak information (how many
    patients exist) and are guessable in a URL. For a system holding health
    data that matters.
    """
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """Adds created_at / updated_at to a model.

    server_default=func.now() means PostgreSQL fills these in, so the value is
    correct even if a row is inserted by a script or by hand.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
