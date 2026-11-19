"""Download the DDInter dataset and load it into PostgreSQL.

Run it inside the API container:

    docker compose exec api python -m scripts.import_ddinter

Options:
    --version 2.0        label stored on every row
    --from-dir ./data    load local CSVs instead of downloading
    --dry-run            parse and report, write nothing

The import is idempotent: rows already present for the same source_version are
skipped, so running it twice is harmless.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import Counter

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models.interaction import DrugInteraction
from app.services.interactions.ddinter import canonical_pair, normalize_key

BASE_URL = "http://ddinter.scbdd.com/static/media/download"

# DDInter splits its data by ATC category. Each letter is one CSV.
CATEGORY_CODES = ["A", "B", "D", "H", "L", "P", "R", "V"]

EXPECTED_COLUMNS = {"DDInterID_A", "Drug_A", "DDInterID_B", "Drug_B", "Level"}

BATCH_SIZE = 2000


def fetch_csv(code: str, timeout: float = 120.0) -> str:
    url = f"{BASE_URL}/ddinter_downloads_code_{code}.csv"
    print(f"  downloading {code} ... ", end="", flush=True)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
    print(f"{len(response.content) / 1_000_000:.1f} MB")
    return response.text


def read_local(path: str, code: str) -> str:
    import pathlib

    file = pathlib.Path(path) / f"ddinter_downloads_code_{code}.csv"
    print(f"  reading {file}")
    return file.read_text(encoding="utf-8")


def parse_rows(text: str, source_version: str) -> list[dict]:
    """Turn one CSV into rows ready for insertion.

    Rows missing a drug name are skipped - a pair with only one side is not a
    usable interaction, and guessing the other half would be inventing data.
    """
    reader = csv.DictReader(io.StringIO(text))

    missing = EXPECTED_COLUMNS - set(reader.fieldnames or [])
    if missing:
        raise ValueError(
            f"CSV is missing expected columns {sorted(missing)}. "
            f"Found: {reader.fieldnames}. The source format may have changed."
        )

    rows: list[dict] = []
    for record in reader:
        name_a = (record.get("Drug_A") or "").strip()
        name_b = (record.get("Drug_B") or "").strip()
        level = (record.get("Level") or "").strip() or "Unknown"

        if not name_a or not name_b:
            continue

        key_a, key_b = canonical_pair(normalize_key(name_a), normalize_key(name_b))
        if key_a == key_b:
            continue  # a drug interacting with itself is not meaningful here

        # Keep display names aligned with the canonical key order.
        display_a, display_b = (
            (name_a, name_b) if normalize_key(name_a) == key_a else (name_b, name_a)
        )

        rows.append(
            {
                "drug_a_key": key_a,
                "drug_b_key": key_b,
                "drug_a_name": display_a,
                "drug_b_name": display_b,
                "level": level,
                "source_name": "DDInter",
                "source_version": source_version,
            }
        )
    return rows


def load(rows: list[dict]) -> int:
    """Insert rows, skipping any pair already stored for this version.

    ON CONFLICT DO NOTHING is what makes the import idempotent at the database
    level rather than relying on the script being careful.
    """
    with SessionLocal() as db:
        # Count before and after rather than trusting rowcount: with
        # ON CONFLICT DO NOTHING and batched inserts the driver may report -1,
        # which produced a nonsense "inserted -81 rows" on the first run.
        before = db.execute(
            select(func.count()).select_from(DrugInteraction)
        ).scalar_one()

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start : start + BATCH_SIZE]
            stmt = insert(DrugInteraction).values(batch)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["drug_a_key", "drug_b_key", "source_version"]
            )
            db.execute(stmt)
        db.commit()

        after = db.execute(
            select(func.count()).select_from(DrugInteraction)
        ).scalar_one()

    return after - before


def main() -> int:
    parser = argparse.ArgumentParser(description="Import DDInter interactions.")
    parser.add_argument("--version", default="2.0")
    parser.add_argument("--from-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"DDInter import (version {args.version})")

    all_rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    levels: Counter[str] = Counter()

    for code in CATEGORY_CODES:
        try:
            text = read_local(args.from_dir, code) if args.from_dir else fetch_csv(code)
        except Exception as exc:  # noqa: BLE001 - one bad file must not kill the run
            print(f"  !! category {code} failed: {exc}")
            continue

        rows = parse_rows(text, args.version)

        # The same pair can appear in several category files.
        for row in rows:
            pair = (row["drug_a_key"], row["drug_b_key"])
            if pair in seen:
                continue
            seen.add(pair)
            all_rows.append(row)
            levels[row["level"]] += 1

        print(f"    {len(rows):,} rows parsed, {len(all_rows):,} unique so far")

    if not all_rows:
        print("Nothing parsed. Aborting without writing.")
        return 1

    print(f"\nUnique interactions: {len(all_rows):,}")
    for level, count in levels.most_common():
        print(f"  {level:<10} {count:,}")

    distinct_drugs = {r["drug_a_key"] for r in all_rows} | {r["drug_b_key"] for r in all_rows}
    print(f"Distinct drugs: {len(distinct_drugs):,}")

    if args.dry_run:
        print("\nDry run - nothing written.")
        return 0

    print("\nWriting to database ...")
    inserted = load(all_rows)
    print(f"Inserted {inserted:,} new rows ({len(all_rows) - inserted:,} already present).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
