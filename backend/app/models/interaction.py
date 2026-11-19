"""Reference data: known drug-drug interactions.

This is NOT patient data. It is a dictionary of facts imported from an
authoritative dataset, which the safety engine looks things up in.

Keeping it in our own database rather than calling an API per request buys
three things:

1. **Reproducibility.** The same medication list produces the same findings
   every time, because the data cannot shift under us mid-demo.
2. **Availability.** No external service can take our core feature down.
3. **Auditability.** Every row records which dataset and which version it came
   from, so a finding can be traced back to a specific release.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import uuid_pk


class DrugInteraction(Base):
    """One documented interaction between two drugs.

    The pair is stored in a canonical order - drug_a_key is always
    alphabetically before drug_b_key - so a lookup only has to check one
    direction instead of two.

    Keys are lowercased generic drug names. We match on those because our
    medications carry a normalized_name from RxNorm, and DDInter is also keyed
    on generic names. When a medication has an rxcui we prefer it; the name is
    the bridge between the two vocabularies.
    """

    __tablename__ = "drug_interactions"
    __table_args__ = (
        UniqueConstraint(
            "drug_a_key", "drug_b_key", "source_version",
            name="uq_interaction_pair_version",
        ),
        # The two lookups the safety engine runs on every medication change.
        Index("ix_interaction_pair", "drug_a_key", "drug_b_key"),
        Index("ix_interaction_rxcui_pair", "drug_a_rxcui", "drug_b_rxcui"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    drug_a_key: Mapped[str] = mapped_column(String(200), nullable=False)
    drug_b_key: Mapped[str] = mapped_column(String(200), nullable=False)

    # RxNorm identifiers, filled in after import by scripts/resolve_rxcuis.py.
    #
    # These matter more than they look. DDInter calls aspirin "Acetylsalicylic
    # acid"; a patient types "aspirin". Matching on names misses that pair
    # entirely - a Major interaction, invisible. RxNorm maps both spellings to
    # RXCUI 1191, so matching on the identifier finds it.
    #
    # Nullable because not every DDInter name resolves, and an unresolved drug
    # must still be matchable by name rather than disappearing.
    drug_a_rxcui: Mapped[str | None] = mapped_column(String(20), index=True)
    drug_b_rxcui: Mapped[str | None] = mapped_column(String(20), index=True)

    # The names as the source wrote them, for display and for citation.
    drug_a_name: Mapped[str] = mapped_column(String(200), nullable=False)
    drug_b_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # The source's own words: "Major", "Moderate", "Minor", "Unknown".
    # Stored raw rather than pre-translated, so a finding can quote the source
    # accurately instead of our interpretation of it.
    level: Mapped[str] = mapped_column(String(30), nullable=False)

    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    source_version: Mapped[str] = mapped_column(String(40), nullable=False)

    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DrugInteraction {self.drug_a_name} + {self.drug_b_name} ({self.level})>"
