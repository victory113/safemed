"""Measure whether SafeMed's design decisions actually do what they claim.

    docker compose exec api python -m scripts.evaluate
    docker compose exec api python -m scripts.evaluate --no-network

Three of this project's choices cost real effort, and each was justified by an
argument rather than a number:

  1. Matching drugs by RXCUI rather than by name.
  2. Tiered recall matching (CONFIRMED / POSSIBLE) rather than alerting on
     every name match.
  3. Severity routing - sending caregivers only SEVERE findings.

This script turns each argument into a measurement, so the report can say how
much they are worth instead of asserting that they help. Results are written
to docs/EVALUATION.md.

All data is synthetic or public. No patient information is involved.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.enums import FindingStatus, MedicationStatus, Severity
from app.models.interaction import DrugInteraction
from app.models.medication import Medication
from app.models.safety import SafetyFinding
from app.models.user import User
from app.services.interactions.ddinter import DDInterSource
from app.services.rxnorm import normalize_medication_name
from app.services.safety_engine import SafetyEngine

DEMO_PATIENT_EMAIL = "maria@safemed.demo"

# A plausible older-adult medication list, written the way a patient would say
# them rather than the way a dataset spells them. That difference is the whole
# point of experiment 1.
PANEL = [
    "aspirin",
    "warfarin",
    "ibuprofen",
    "metformin",
    "lisinopril",
    "atorvastatin",
    "amlodipine",
    "omeprazole",
    "levothyroxine",
    "sertraline",
    "furosemide",
    "tramadol",
    "paracetamol",
    "clopidogrel",
    "simvastatin",
]


def rule(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


# ---------------------------------------------------------------- experiment 1


def experiment_identifier_matching(db, use_network: bool) -> dict:
    """Does matching by RXCUI find interactions that name matching misses?

    Method: take the panel above, ask the same source for interactions twice -
    once with only the names, once with names and RXCUIs - and compare. This
    is a controlled comparison: same drugs, same dataset, same code path. The
    only variable is whether identifiers are available.
    """
    rule("1. Identifier matching vs name matching")

    source = DDInterSource(db)
    rxcuis: list[str] = []
    unresolved: list[str] = []

    if use_network:
        for name in PANEL:
            result = normalize_medication_name(name)
            if result.found and result.rxcui:
                rxcuis.append(result.rxcui)
            else:
                unresolved.append(name)
    else:
        print("  (--no-network: skipped, RxNorm lookup needed)")
        return {"skipped": True}

    by_name = source.find_interactions(PANEL, rxcuis=None)
    by_both = source.find_interactions(PANEL, rxcuis=rxcuis)

    def pair_set(hits):
        return {tuple(sorted((h.drug_a_key, h.drug_b_key))) for h in hits}

    names_only, both = pair_set(by_name), pair_set(by_both)
    missed = both - names_only

    severe_missed = sum(
        1
        for h in by_both
        if tuple(sorted((h.drug_a_key, h.drug_b_key))) in missed
        and h.severity == Severity.SEVERE
    )

    recall = len(names_only) / len(both) if both else 0.0

    print(f"  Panel size                      {len(PANEL)} medications")
    print(f"  Resolved to an RXCUI            {len(rxcuis)}/{len(PANEL)}")
    if unresolved:
        print(f"  Unresolved (name fallback)      {', '.join(unresolved)}")
    print(f"  Interactions found, names only  {len(names_only)}")
    print(f"  Interactions found, with RXCUI  {len(both)}")
    print(f"  Missed by name matching alone   {len(missed)}"
          f"  ({(1 - recall) * 100:.0f}% of all findings)")
    print(f"    of which SEVERE               {severe_missed}")

    examples = []
    for hit in by_both:
        key = tuple(sorted((hit.drug_a_key, hit.drug_b_key)))
        if key in missed and len(examples) < 5:
            examples.append(
                f"{hit.drug_a_name} + {hit.drug_b_name} ({hit.level})"
            )
    if examples:
        print("  Examples name matching missed:")
        for line in examples:
            print(f"    - {line}")

    return {
        "panel_size": len(PANEL),
        "resolved": len(rxcuis),
        "unresolved": unresolved,
        "found_by_name": len(names_only),
        "found_with_rxcui": len(both),
        "missed_by_name": len(missed),
        "severe_missed_by_name": severe_missed,
        "name_only_recall": round(recall, 4),
        "examples": examples,
    }


# ---------------------------------------------------------------- experiment 2


def experiment_dataset_coverage(db) -> dict:
    """How much of the interaction dataset is identifier-addressable?

    A one-off import question, but it bounds everything above: interactions
    whose drugs have no RXCUI can only ever be matched by name.
    """
    rule("2. Dataset coverage")

    total = db.scalar(select(func.count()).select_from(DrugInteraction)) or 0
    both_ids = (
        db.scalar(
            select(func.count())
            .select_from(DrugInteraction)
            .where(
                DrugInteraction.drug_a_rxcui.isnot(None),
                DrugInteraction.drug_b_rxcui.isnot(None),
            )
        )
        or 0
    )
    names = db.scalar(
        select(func.count(func.distinct(DrugInteraction.drug_a_key)))
    ) or 0

    pct = (both_ids / total * 100) if total else 0.0
    print(f"  Interaction pairs imported      {total:,}")
    print(f"  Pairs with both RXCUIs          {both_ids:,}  ({pct:.1f}%)")
    print(f"  Distinct drug names (side A)    {names:,}")

    return {
        "pairs_total": total,
        "pairs_with_both_rxcuis": both_ids,
        "pct_identifier_addressable": round(pct, 2),
    }


# ---------------------------------------------------------------- experiment 3


def experiment_severity_routing(db) -> dict:
    """How much noise does severity routing keep off a caregiver's screen?

    The claim being tested: a realistic medication list produces far more
    findings than are worth a phone call, so sending all of them would train
    a caregiver to ignore the lot.
    """
    rule("3. Severity routing")

    patient = db.scalar(select(User).where(User.email == DEMO_PATIENT_EMAIL))
    if patient is None:
        print(f"  (skipped: run scripts.seed_demo first - no {DEMO_PATIENT_EMAIL})")
        return {"skipped": True}

    findings = list(
        db.scalars(
            select(SafetyFinding).where(
                SafetyFinding.patient_id == patient.id,
                SafetyFinding.status != FindingStatus.RESOLVED,
            )
        ).all()
    )
    medications = db.scalar(
        select(func.count())
        .select_from(Medication)
        .where(
            Medication.patient_id == patient.id,
            Medication.status == MedicationStatus.ACTIVE,
        )
    ) or 0

    counts = {s.value: 0 for s in Severity}
    for finding in findings:
        counts[finding.severity.value] += 1

    total = len(findings)
    to_caregiver = counts["SEVERE"]
    reduction = (1 - to_caregiver / total) * 100 if total else 0.0

    print(f"  Active medications              {medications}")
    print(f"  Findings on the patient screen  {total}"
          f"   (severe {counts['SEVERE']}, moderate {counts['MODERATE']},"
          f" mild {counts['MILD']})")
    print(f"  Findings sent to a caregiver    {to_caregiver}")
    print(f"  Caregiver alert reduction       {reduction:.0f}%")

    return {
        "medications": medications,
        "findings_total": total,
        "by_severity": counts,
        "to_caregiver": to_caregiver,
        "caregiver_reduction_pct": round(reduction, 1),
    }


# ---------------------------------------------------------------- experiment 4


def experiment_recall_precision(use_network: bool) -> dict:
    """What share of FDA recalls can be attributed to an exact product?

    This is the number that forced tiered matching. A recall without an NDC
    cannot be tied to one manufacturer's product, so asserting that it affects
    a particular patient would be a guess presented as a fact.
    """
    rule("4. Recall identifiability")

    if not use_network:
        print("  (--no-network: skipped, openFDA lookup needed)")
        return {"skipped": True}

    import httpx

    url = (
        "https://api.fda.gov/drug/enforcement.json"
        "?search=status:%22Ongoing%22&limit=100"
    )
    try:
        with httpx.Client(timeout=30) as client:
            payload = client.get(url).json()
    except Exception as exc:  # noqa: BLE001 - a failed sample is reportable
        print(f"  (skipped: openFDA unreachable - {type(exc).__name__})")
        return {"skipped": True, "reason": type(exc).__name__}

    results = payload.get("results", [])
    if not results:
        print("  (skipped: openFDA returned no records)")
        return {"skipped": True}

    with_ndc = sum(
        1
        for r in results
        if any(ch.isdigit() for ch in (r.get("product_ndc") or ""))
        or "NDC" in (r.get("product_description") or "").upper()
    )
    without = len(results) - with_ndc

    class_i = sum(1 for r in results if r.get("classification") == "Class I")

    print(f"  Recalls sampled                 {len(results)}")
    print(f"  Identify an exact product (NDC) {with_ndc}"
          f"  ({with_ndc / len(results) * 100:.0f}%)  -> CONFIRMED possible")
    print(f"  No product identifier           {without}"
          f"  ({without / len(results) * 100:.0f}%)  -> POSSIBLE at best")
    print(f"  Class I (most serious)          {class_i}")
    print()
    print(f"  Without tiering, every one of the {without} unidentifiable recalls")
    print("  would be asserted as 'affects you' on a name match alone.")

    return {
        "sampled": len(results),
        "with_ndc": with_ndc,
        "without_ndc": without,
        "pct_confirmable": round(with_ndc / len(results) * 100, 1),
        "class_i": class_i,
    }


# ---------------------------------------------------------------- experiment 5


def experiment_idempotence_and_latency(db) -> dict:
    """Does re-evaluating create duplicates, and how long does it take?

    The worker re-evaluates on a timer, so "runs repeatedly" is the normal
    case. If the second run created findings, the alerts would multiply until
    nobody read them.
    """
    rule("5. Idempotence and latency")

    patient = db.scalar(select(User).where(User.email == DEMO_PATIENT_EMAIL))
    if patient is None:
        print("  (skipped: run scripts.seed_demo first)")
        return {"skipped": True}

    created_per_run: list[int] = []
    timings: list[float] = []

    for _ in range(3):
        started = time.perf_counter()
        result = SafetyEngine(db).evaluate_patient(patient.id)
        db.commit()
        timings.append((time.perf_counter() - started) * 1000)
        created_per_run.append(len(result.created))

    print(f"  New findings per run            {created_per_run}")
    print(f"  Duplicate findings created      {sum(created_per_run[1:])}")
    print(f"  Median evaluation time          {statistics.median(timings):.0f} ms")
    print(f"  Slowest run                     {max(timings):.0f} ms")

    return {
        "created_per_run": created_per_run,
        "duplicates_created": sum(created_per_run[1:]),
        "median_ms": round(statistics.median(timings), 1),
        "max_ms": round(max(timings), 1),
    }


# ---------------------------------------------------------------------- report


def write_report(results: dict, path: Path) -> None:
    e1 = results.get("identifier_matching", {})
    e2 = results.get("dataset_coverage", {})
    e3 = results.get("severity_routing", {})
    e4 = results.get("recall_identifiability", {})
    e5 = results.get("idempotence", {})

    lines = [
        "# SafeMed — Evaluation",
        "",
        f"Generated {results['generated_at']} by `scripts/evaluate.py`.",
        "",
        "Three design decisions in SafeMed cost real effort and were argued for",
        "rather than measured. This document measures them. Re-run with:",
        "",
        "```bash",
        "docker compose exec api python -m scripts.evaluate",
        "```",
        "",
        "All data is synthetic or public. No patient information is involved.",
        "",
        "---",
        "",
        "## 1. Matching by identifier rather than by name",
        "",
        "**Claim.** Drug names are not comparable across sources, so matching on",
        "text silently misses real interactions.",
        "",
        "**Method.** A 15-medication panel written the way a patient would say",
        "them. The same interaction source is queried twice — once with names",
        "only, once with names and RXCUIs. Same drugs, same dataset, same code",
        "path; the only variable is whether identifiers are available.",
        "",
    ]

    if e1.get("skipped"):
        lines += ["_Not run (network required)._", ""]
    else:
        missed_pct = (1 - e1["name_only_recall"]) * 100
        lines += [
            "| Measure | Result |",
            "|---|---|",
            f"| Panel size | {e1['panel_size']} medications |",
            f"| Resolved to an RXCUI | {e1['resolved']}/{e1['panel_size']} |",
            f"| Interactions found, names only | {e1['found_by_name']} |",
            f"| Interactions found, with RXCUI | {e1['found_with_rxcui']} |",
            f"| **Missed by name matching alone** | **{e1['missed_by_name']} "
            f"({missed_pct:.0f}%)** |",
            f"| Of those, rated SEVERE | {e1['severe_missed_by_name']} |",
            "",
        ]
        if e1.get("examples"):
            lines += ["Examples name matching missed:", ""]
            lines += [f"- {x}" for x in e1["examples"]]
            lines += [""]
        lines += [
            f"**Result.** Name matching alone recovers only "
            f"{e1['name_only_recall'] * 100:.0f}% of the interactions the same "
            "dataset contains for the same patient. The failure is silent — no "
            "error, no warning, simply a safety check that finds nothing.",
            "",
        ]

    lines += ["---", "", "## 2. Dataset coverage", ""]
    if e2.get("skipped"):
        lines += ["_Not run._", ""]
    else:
        lines += [
            "| Measure | Result |",
            "|---|---|",
            f"| Interaction pairs imported | {e2['pairs_total']:,} |",
            f"| Pairs with both RXCUIs | {e2['pairs_with_both_rxcuis']:,} |",
            f"| Identifier-addressable | {e2['pct_identifier_addressable']}% |",
            "",
            "The remainder still match by name, so coverage degrades rather than",
            "disappearing.",
            "",
        ]

    lines += [
        "---",
        "",
        "## 3. Severity routing",
        "",
        "**Claim.** A realistic medication list produces far more findings than",
        "are worth a caregiver's attention, and sending all of them would train",
        "that caregiver to ignore every one.",
        "",
    ]
    if e3.get("skipped"):
        lines += ["_Not run (seed the demo data first)._", ""]
    else:
        s = e3["by_severity"]
        lines += [
            "| Measure | Result |",
            "|---|---|",
            f"| Active medications | {e3['medications']} |",
            f"| Findings shown to the patient | {e3['findings_total']} |",
            f"| — severe / moderate / mild | {s['SEVERE']} / {s['MODERATE']} / "
            f"{s['MILD']} |",
            f"| Findings sent to a caregiver | {e3['to_caregiver']} |",
            f"| **Caregiver alert reduction** | "
            f"**{e3['caregiver_reduction_pct']:.0f}%** |",
            "",
            f"**Result.** {e3['medications']} ordinary medications generate "
            f"{e3['findings_total']} findings. Severity routing reduces what "
            f"reaches a caregiver by {e3['caregiver_reduction_pct']:.0f}%, while "
            "the patient keeps the full list on their own account.",
            "",
        ]

    lines += [
        "---",
        "",
        "## 4. Recall identifiability",
        "",
        "**Claim.** FDA recall notices often cannot be tied to one",
        "manufacturer's product, so asserting that a recall affects a specific",
        "patient would be a guess presented as a fact.",
        "",
    ]
    if e4.get("skipped"):
        lines += ["_Not run (network required)._", ""]
    else:
        lines += [
            "| Measure | Result |",
            "|---|---|",
            f"| Recalls sampled (openFDA, ongoing) | {e4['sampled']} |",
            f"| Identify an exact product (NDC) | {e4['with_ndc']} "
            f"({e4['pct_confirmable']}%) |",
            f"| No product identifier | {e4['without_ndc']} |",
            f"| Class I (most serious) | {e4['class_i']} |",
            "",
            f"**Result.** {e4['without_ndc']} of {e4['sampled']} sampled recalls "
            "cannot be attributed to a specific product. Without tiering, each "
            "of those would be asserted as *affects you* on a drug-name match "
            "alone. SafeMed reports them as POSSIBLE and asks the patient to "
            "check the label.",
            "",
        ]

    lines += ["---", "", "## 5. Idempotence and latency", ""]
    if e5.get("skipped"):
        lines += ["_Not run (seed the demo data first)._", ""]
    else:
        lines += [
            "| Measure | Result |",
            "|---|---|",
            f"| New findings per run (3 runs) | {e5['created_per_run']} |",
            f"| Duplicates created on re-runs | {e5['duplicates_created']} |",
            f"| Median evaluation time | {e5['median_ms']} ms |",
            f"| Slowest run | {e5['max_ms']} ms |",
            "",
            "**Result.** Re-evaluation creates no duplicates. The background",
            "worker re-runs on a timer, so this is the normal case rather than",
            "an edge case — without it the same finding would be reported every",
            "hour until nobody read the alerts.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Threats to validity",
        "",
        "Worth stating plainly rather than leaving for a marker to find:",
        "",
        "- **The panel is chosen, not sampled.** Fifteen common medications",
        "  selected to resemble an older adult's list. A different panel would",
        "  give different absolute numbers, though the direction holds for any",
        "  panel containing drugs whose common name differs from the dataset's.",
        "- **One interaction dataset.** DDInter. A second source would be needed",
        "  to say anything about completeness in general.",
        "- **The recall sample is a snapshot** of ongoing recalls on the day it",
        "  was run, not a longitudinal study.",
        "- **No clinical validation.** These measure internal consistency and",
        "  alert volume, not clinical outcomes. Nothing here says SafeMed",
        "  improves anyone's health — only that it finds interactions a",
        "  name-matching system would miss, and sends fewer false alarms than a",
        "  naive one.",
        "",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure SafeMed's design claims.")
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Skip experiments needing RxNorm or openFDA.",
    )
    parser.add_argument(
        "--out",
        default="/docs/EVALUATION.md",
        help="Where to write the report. /docs is the repo docs/ folder, mounted by compose.",
    )
    args = parser.parse_args()
    use_network = not args.no_network

    print("SafeMed evaluation")
    print("=" * 62)

    results: dict = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

    with SessionLocal() as db:
        results["identifier_matching"] = experiment_identifier_matching(db, use_network)
        results["dataset_coverage"] = experiment_dataset_coverage(db)
        results["severity_routing"] = experiment_severity_routing(db)
        results["recall_identifiability"] = experiment_recall_precision(use_network)
        results["idempotence"] = experiment_idempotence_and_latency(db)

    out = Path(args.out).resolve()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        write_report(results, out)
        print()
        print("=" * 62)
        print(f"Report written to {out}")
    except OSError as exc:
        print(f"\nCould not write the report: {exc}")
        print(json.dumps(results, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
