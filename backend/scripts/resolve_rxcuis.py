"""Resolve DDInter drug names to RxNorm identifiers.

Run after importing the dataset:

    docker compose exec api python -m scripts.resolve_rxcuis

WHY THIS IS A SEPARATE STEP
---------------------------
DDInter is keyed on its own drug names. Our patients' medications are keyed on
RXCUI, because that is what RxNorm gives us. Without a bridge between the two,
a patient taking "aspirin" is never matched against DDInter's
"Acetylsalicylic acid" - and that pair with warfarin is a Major interaction we
would simply never report.

So we resolve each distinct DDInter drug name once, store the RXCUI on every
row that mentions it, and from then on the safety engine matches identifiers.

There are roughly 1,900 distinct drugs, so this takes a few minutes. It only
needs running once per dataset version, and it is safe to re-run - already
resolved names are skipped unless --all is given.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import or_, select, update

from app.db.session import SessionLocal
from app.models.interaction import DrugInteraction
from app.services.rxnorm import RxNormClient


def distinct_unresolved(db, include_all: bool) -> list[str]:
    """Every drug key that still has no RXCUI stored."""
    a = select(DrugInteraction.drug_a_key, DrugInteraction.drug_a_rxcui)
    b = select(DrugInteraction.drug_b_key, DrugInteraction.drug_b_rxcui)

    keys: dict[str, str | None] = {}
    for key, rxcui in db.execute(a.union(b)).all():
        # Keep a resolved value if any row already has one.
        if key not in keys or keys[key] is None:
            keys[key] = rxcui

    if include_all:
        return sorted(keys)
    return sorted(k for k, v in keys.items() if v is None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve DDInter names to RXCUIs.")
    parser.add_argument("--all", action="store_true",
                        help="re-resolve names that already have an RXCUI")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after N names (useful for a quick check)")
    args = parser.parse_args()

    client = RxNormClient()
    resolved = unresolved = 0

    with SessionLocal() as db:
        names = distinct_unresolved(db, args.all)
        if args.limit:
            names = names[: args.limit]

        print(f"Resolving {len(names):,} drug names via RxNorm ...")

        for index, key in enumerate(names, start=1):
            result = client.normalize(key)

            if result.found:
                db.execute(
                    update(DrugInteraction)
                    .where(DrugInteraction.drug_a_key == key)
                    .values(drug_a_rxcui=result.rxcui)
                )
                db.execute(
                    update(DrugInteraction)
                    .where(DrugInteraction.drug_b_key == key)
                    .values(drug_b_rxcui=result.rxcui)
                )
                resolved += 1
            else:
                unresolved += 1

            if index % 100 == 0:
                db.commit()
                print(f"  {index:,}/{len(names):,}  resolved={resolved:,}  unmatched={unresolved:,}")

        db.commit()

    total = resolved + unresolved
    rate = (resolved / total * 100) if total else 0.0
    print(f"\nDone. Resolved {resolved:,} of {total:,} ({rate:.1f}%).")
    print("Unresolved drugs remain matchable by name - they are not lost.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
