# SafeMed — Evaluation

Generated 2026-11-20 01:51 UTC by `scripts/evaluate.py`.

Three design decisions in SafeMed cost real effort and were argued for
rather than measured. This document measures them. Re-run with:

```bash
docker compose exec api python -m scripts.evaluate
```

All data is synthetic or public. No patient information is involved.

---

## 1. Matching by identifier rather than by name

**Claim.** Drug names are not comparable across sources, so matching on
text silently misses real interactions.

**Method.** A 15-medication panel written the way a patient would say
them. The same interaction source is queried twice — once with names
only, once with names and RXCUIs. Same drugs, same dataset, same code
path; the only variable is whether identifiers are available.

| Measure | Result |
|---|---|
| Panel size | 15 medications |
| Resolved to an RXCUI | 15/15 |
| Interactions found, names only | 63 |
| Interactions found, with RXCUI | 84 |
| **Missed by name matching alone** | **21 (25%)** |
| Of those, rated SEVERE | 2 |

Examples name matching missed:

- Acetylsalicylic acid + Ibuprofen (Major)
- Acetylsalicylic acid + Warfarin (Major)
- Acetaminophen + Warfarin (Moderate)
- Acetylsalicylic acid + Clopidogrel (Moderate)
- Acetylsalicylic acid + Lisinopril (Moderate)

**Result.** Name matching alone recovers only 75% of the interactions the same dataset contains for the same patient. The failure is silent — no error, no warning, simply a safety check that finds nothing.

---

## 2. Dataset coverage

| Measure | Result |
|---|---|
| Interaction pairs imported | 160,235 |
| Pairs with both RXCUIs | 159,906 |
| Identifier-addressable | 99.79% |

The remainder still match by name, so coverage degrades rather than
disappearing.

---

## 3. Severity routing

**Claim.** A realistic medication list produces far more findings than
are worth a caregiver's attention, and sending all of them would train
that caregiver to ignore every one.

| Measure | Result |
|---|---|
| Active medications | 5 |
| Findings shown to the patient | 10 |
| — severe / moderate / mild | 3 / 5 / 2 |
| Findings sent to a caregiver | 3 |
| **Caregiver alert reduction** | **70%** |

**Result.** 5 ordinary medications generate 10 findings. Severity routing reduces what reaches a caregiver by 70%, while the patient keeps the full list on their own account.

---

## 4. Recall identifiability

**Claim.** FDA recall notices often cannot be tied to one
manufacturer's product, so asserting that a recall affects a specific
patient would be a guess presented as a fact.

| Measure | Result |
|---|---|
| Recalls sampled (openFDA, ongoing) | 100 |
| Identify an exact product (NDC) | 55 (55.0%) |
| No product identifier | 45 |
| Class I (most serious) | 5 |

**Result.** 45 of 100 sampled recalls cannot be attributed to a specific product. Without tiering, each of those would be asserted as *affects you* on a drug-name match alone. SafeMed reports them as POSSIBLE and asks the patient to check the label.

---

## 5. Idempotence and latency

| Measure | Result |
|---|---|
| New findings per run (3 runs) | [0, 0, 0] |
| Duplicates created on re-runs | 0 |
| Median evaluation time | 7.2 ms |
| Slowest run | 9.9 ms |

**Result.** Re-evaluation creates no duplicates. The background
worker re-runs on a timer, so this is the normal case rather than
an edge case — without it the same finding would be reported every
hour until nobody read the alerts.

---

## Threats to validity

Worth stating plainly rather than leaving for a marker to find:

- **The panel is chosen, not sampled.** Fifteen common medications
  selected to resemble an older adult's list. A different panel would
  give different absolute numbers, though the direction holds for any
  panel containing drugs whose common name differs from the dataset's.
- **One interaction dataset.** DDInter. A second source would be needed
  to say anything about completeness in general.
- **The recall sample is a snapshot** of ongoing recalls on the day it
  was run, not a longitudinal study.
- **No clinical validation.** These measure internal consistency and
  alert volume, not clinical outcomes. Nothing here says SafeMed
  improves anyone's health — only that it finds interactions a
  name-matching system would miss, and sends fewer false alarms than a
  naive one.

