# SafeMed — Software Requirements Specification

**CSCI 4490 Software Engineering · Fall 2026 · University of Central Arkansas**
Victory Orobosa (Project Leader, Full-Stack) · Chima Onochie (Backend & Data Integration) · Pacifique Mugisha (Security, Testing & Deployment)

Document version 1.0 · 24 November 2026

---

## 1. Purpose and Scope

### 1.1 Purpose

This document specifies the requirements for **SafeMed**, a continuous
medication safety monitoring and caregiver alert platform. It states what the
system must do, what it must not do, and how each requirement can be verified.

### 1.2 Scope

SafeMed allows a patient to record the medications they take, continuously
checks that list against authoritative drug-interaction and FDA recall data,
and surfaces any potential safety issue to the patient — and, where the
patient has explicitly authorized it, to a caregiver.

**In scope:** medication management, dose scheduling and adherence tracking,
deterministic safety evaluation, FDA recall monitoring, consent-based
caregiver access, role-based access control, an append-only audit trail, and
an AI layer restricted to explaining findings already produced.

**Out of scope:** prescribing, diagnosis, clinical decision-making, pharmacy
integration, insurance claims, real patient data, and any use as a regulated
medical device.

### 1.3 Definitions

| Term | Meaning |
|---|---|
| **RXCUI** | RxNorm Concept Unique Identifier; a stable numeric id for a drug concept |
| **NDC** | National Drug Code; identifies a specific product *and* its manufacturer |
| **DDInter** | An open-access, peer-reviewed drug–drug interaction dataset |
| **Finding** | A recorded potential safety issue, with its source and severity |
| **Grant** | A patient's explicit, revocable authorization for one caregiver |
| **Dedupe key** | A hash of a finding's subject, used so re-evaluation creates no duplicates |

### 1.4 Operating environment

Containerised deployment: PostgreSQL 16, Redis 7, a FastAPI application
server, a Celery worker and a Celery Beat scheduler, with a React + TypeScript
single-page frontend. All services are defined in `docker-compose.yml`.

---

## 2. Business Requirements (BR)

| ID | Requirement | Rationale |
|---|---|---|
| **BR-01** | Reduce preventable harm from drug–drug interactions by surfacing them to the person taking the medication. | The information is public but is not where the patient is. |
| **BR-02** | Continue checking after the user stops interacting with the system. | New recalls and new interaction data arrive after a medication is entered. |
| **BR-03** | Allow a trusted family member to be informed without surrendering control of the record. | Caregiving is normal; unsupervised access to a medical record is not. |
| **BR-04** | Make every safety claim attributable to a named, checkable source. | An unsourced warning cannot be acted on by a pharmacist. |
| **BR-05** | Remain outside the regulatory definition of a medical device. | A student project must not diagnose, prescribe, or direct treatment. |

---

## 3. User Requirements (UR)

| ID | As a… | I want to… | So that… | From |
|---|---|---|---|---|
| **UR-01** | Patient | record the medications I take, with the times I take them | the system has something to check and to remind me about | BR-01 |
| **UR-02** | Patient | be told when two of my medications interact | I can raise it with my pharmacist | BR-01 |
| **UR-03** | Patient | be told when one of my medications is recalled | I can check whether my specific product is affected | BR-02 |
| **UR-04** | Patient | confirm each day that I took a dose | I can see whether I am keeping up | BR-01 |
| **UR-05** | Patient | invite a caregiver, and remove them at any time | I stay in control of who sees my record | BR-03 |
| **UR-06** | Caregiver | see only the serious alerts for someone who invited me | I am useful without being overwhelmed or intrusive | BR-03 |
| **UR-07** | Caregiver | see whether they have been taking their medication | I can notice a problem early | BR-03 |
| **UR-08** | Patient | see where each warning came from | I can judge whether to trust it | BR-04 |
| **UR-09** | Patient | know that nobody read my record without it being recorded | consent means something | BR-03 |
| **UR-10** | Any user | have warnings explained in plain language | I can understand them without clinical training | BR-01 |

---

## 4. Functional Requirements (FR)

Each requirement states its verification method. "Test" names a real test in
`backend/tests/`.

### 4.1 Accounts and access

| ID | Requirement | Verification |
|---|---|---|
| **FR-01** | The system shall allow a user to register with an email address, password and role (PATIENT or CAREGIVER), and shall store only a hashed password. | `test_consent.py` — registration and login via HTTP |
| **FR-02** | The system shall issue a signed, expiring token on successful login, and reject any request presenting an invalid, expired or absent token. | `test_consent.py`; `app/core/security.py` |
| **FR-03** | The system shall restrict every endpoint to the roles permitted to use it, enforced on the server independently of the client. | `test_consent.py`, `test_caregiver_views.py` |

### 4.2 Medication management

| ID | Requirement | Verification |
|---|---|---|
| **FR-04** | The system shall allow a patient to record a medication with, at minimum, a name; all other fields shall be optional. | `test_medication_repository.py`, `app/schemas/medication.py` |
| **FR-05** | The system shall resolve each recorded medication to an RXCUI via RxNorm, and shall still save the medication if that resolution fails. | `test_rxnorm.py` (9 tests) |
| **FR-06** | The system shall allow a patient to record one or more times of day for a medication, each becoming a dose schedule. | `test_doses_api.py` |
| **FR-07** | The system shall allow a patient to stop a medication, and shall retain the stopped record rather than deleting it. | `test_audit_resilience.py::test_stopping_a_medication_is_audited_and_the_creation_row_survives` |

### 4.3 Safety evaluation

| ID | Requirement | Verification |
|---|---|---|
| **FR-08** | The system shall evaluate a patient's full active medication list for pairwise interactions using an authoritative dataset, without using AI to make the determination. | `test_safety_engine.py` (13 tests), `test_interactions.py` (17 tests) |
| **FR-09** | The system shall match interacting drugs by RXCUI where available, falling back to name matching only when no identifier exists. | `test_interactions.py`; measured in `docs/EVALUATION.md` |
| **FR-10** | The system shall record, with every finding, its source name, source version and the medications involved. | `app/models/safety.py`; `test_safety_engine.py` |
| **FR-11** | The system shall assign each finding a severity of MILD, MODERATE or SEVERE derived from the source data, not inferred. | `test_safety_engine.py` |
| **FR-12** | Re-evaluating an unchanged medication list shall create no additional findings. | `test_safety_engine.py`; dedupe key in `app/models/safety.py` |

### 4.4 Recall monitoring

| ID | Requirement | Verification |
|---|---|---|
| **FR-13** | The system shall query the FDA openFDA enforcement API on a schedule without user interaction. | `app/workers/celery_app.py` (`check-fda-recalls-hourly`); `test_recall_monitor.py` |
| **FR-14** | The system shall classify a recall match as CONFIRMED only when the recall identifies the exact product the patient holds, and as POSSIBLE otherwise. | `test_recalls.py` (16 tests) |
| **FR-15** | The wording presented for a POSSIBLE match shall ask the patient to check their label rather than state that they are affected. | `test_recalls.py`; verified in demo |
| **FR-16** | Repeated runs of the recall check shall not create duplicate findings. | `test_recall_monitor.py`; measured in `docs/EVALUATION.md` (0 duplicates over 3 runs) |

### 4.5 Adherence

| ID | Requirement | Verification |
|---|---|---|
| **FR-17** | The system shall generate dose events from active schedules and present the doses due today. | `test_dose_scheduler.py` (13 tests) |
| **FR-18** | The system shall allow a patient to confirm or skip a dose, and shall distinguish a skipped dose from a missed one in adherence figures. | `test_doses_api.py` (18 tests) |
| **FR-19** | A dose shall be marked MISSED only after its grace period has elapsed without confirmation. | `test_dose_scheduler.py` |
| **FR-20** | Doses scheduled at the same time shall be returned in a stable, repeatable order. | `test_dose_repository.py::test_doses_at_the_same_time_come_back_in_a_stable_order` |

### 4.6 Consent and caregiver access

| ID | Requirement | Verification |
|---|---|---|
| **FR-21** | A patient shall be able to invite a caregiver by email address, creating a PENDING grant. | `test_consent.py` (24 tests) |
| **FR-22** | A caregiver shall see a patient's data only through an ACTIVE grant, re-checked on every request. | `test_consent.py`, `test_caregiver_views.py` |
| **FR-23** | A patient shall be able to revoke a grant, taking effect on the caregiver's next request rather than at session expiry. | `test_consent.py` |
| **FR-24** | A revoked grant shall be retained, not deleted. | `test_audit_hooks.py::test_the_whole_history_is_kept_after_a_revoke` |
| **FR-25** | A caregiver shall be shown only findings of severity SEVERE. | `test_caregiver_views.py` (13 tests); measured at 70% reduction in `docs/EVALUATION.md` |
| **FR-26** | A caregiver shall have read-only access; they shall not be able to record a dose or alter a medication on a patient's behalf. | `test_caregiver_views.py` |
| **FR-27** | A request for a patient that does not exist and a request for a patient the caregiver has no grant for shall produce identical responses. | `test_consent.py`; `app/api/deps.py` |

### 4.7 Audit

| ID | Requirement | Verification |
|---|---|---|
| **FR-28** | The system shall record every consent invitation, acceptance and revocation. | `test_audit_hooks.py` (10 tests) |
| **FR-29** | The system shall record every occasion on which a caregiver reads a patient's record. | `test_audit_hooks.py::test_every_caregiver_view_records_who_looked_at_whom` |
| **FR-30** | The system shall record every refused attempt to read a patient's record, under an action distinct from a successful read. | `test_audit_resilience.py::test_a_refused_attempt_is_recorded_under_its_own_action` |
| **FR-31** | The system shall record creation, modification and stopping of a medication; a modification shall record which fields changed, not their values. | `test_audit_resilience.py::test_an_update_records_which_fields_changed_not_their_values` |
| **FR-32** | The application shall not permit any audit record to be modified or deleted. | `test_audit.py::test_an_audit_row_cannot_be_updated`, `::test_an_audit_row_cannot_be_deleted` |
| **FR-33** | An audit record for a write shall be committed in the same transaction as the action it describes, so that a rolled-back action leaves no record. | `test_audit.py::test_the_row_rolls_back_with_the_callers_transaction` |
| **FR-34** | A refusal record shall not disclose whether the requested patient exists. | `test_audit_resilience.py::test_a_refusal_does_not_confirm_the_patient_exists` |

### 4.8 Presentation

| ID | Requirement | Verification |
|---|---|---|
| **FR-35** | The patient interface shall present SEVERE findings expanded and announced to assistive technology, and lesser findings collapsed. | `frontend/src/pages/dashboard/SafetyFindings.tsx`; manual review |
| **FR-36** | The caregiver interface shall state explicitly that it is showing serious findings only. | `frontend/src/pages/caregiver/CaregiverDashboard.tsx` |
| **FR-37** | A failed request shall produce a visible message rather than an empty screen. | `frontend/src/api/client.ts`; `test_audit_resilience.py` for the server side |

---

## 5. Non-Functional Requirements (NFR)

| ID | Category | Requirement | Verification |
|---|---|---|---|
| **NFR-01** | Security | Passwords shall be stored only as salted hashes; the signing key shall have no default and the application shall refuse to start without it. | `app/core/config.py`, `app/core/security.py` |
| **NFR-02** | Security | Authorization shall be enforced server-side on every request; client-side routing shall be treated as convenience only. | `test_caregiver_views.py`; documented in HANDBOOK §8.3 |
| **NFR-03** | Privacy | No patient identifier shall be transmitted to any third-party AI service. | `test_ai_explainer.py` (11 tests); HANDBOOK §7.3 |
| **NFR-04** | Privacy | Development and demonstration shall use synthetic data only. | `backend/scripts/seed_demo.py` |
| **NFR-05** | Reliability | Failure of any external service shall degrade functionality, not prevent it. | `test_rxnorm.py`, `test_recall_monitor.py`, `test_ai_explainer.py` |
| **NFR-06** | Reliability | Background jobs shall be idempotent. | `docs/EVALUATION.md` — 0 duplicates across 3 full re-runs |
| **NFR-07** | Performance | Safety evaluation of a realistic medication list shall complete within one second. | `docs/EVALUATION.md` — 7 ms median |
| **NFR-08** | Accessibility | The interface shall use a minimum 18px base text size, minimum 44px touch targets, and shall never use colour as the only carrier of meaning. | `frontend/src/styles/`; HANDBOOK §8.5 |
| **NFR-09** | Maintainability | The interaction data source shall sit behind an interface so it can be replaced without altering the safety engine. | `app/services/interactions/`; HANDBOOK §5 |
| **NFR-10** | Verifiability | Every push shall run the full automated test suite, type checking, linting and a migration check. | `.github/workflows/ci.yml` |
| **NFR-11** | Portability | The complete system shall reach a running, seeded state from a clean checkout with one command, requiring no host toolchain beyond Docker. | `scripts/setup.ps1`, `scripts/setup.sh`; equivalent manual steps in `README.md` and `docs/SETUP.md` |

---

## 6. AI Requirements (AIR)

| ID | Requirement | Verification |
|---|---|---|
| **AIR-01** | AI shall never determine whether a medication combination is dangerous. That determination shall come from the deterministic engine before any model is invoked. | Architecture; `test_safety_engine.py` passes with AI disabled |
| **AIR-02** | AI input shall contain drug names and source text only — never a patient name, identifier, age, email or medication list. | `test_ai_explainer.py` |
| **AIR-03** | Every AI response shall be validated before storage and discarded if it instructs the reader to stop, change or adjust a medication. | `test_ai_explainer.py` — 11 forbidden patterns |
| **AIR-04** | Every AI response shall direct the reader to a pharmacist or healthcare provider. | `test_ai_explainer.py` — required pattern |
| **AIR-05** | Disabling AI entirely shall leave every finding complete and displayable. | `test_explain_findings.py`; `ai_explanation` is nullable by design |

---

## 7. Boundary Constraints (BC)

Constraints that override every other requirement in this document.

| ID | Constraint |
|---|---|
| **BC-01** | SafeMed shall not diagnose a condition, prescribe a medication, or instruct any user to start, stop, or change a medication or dose. Every finding shall direct the user to a qualified professional. |
| **BC-02** | SafeMed shall not process real patient medical records. All development, testing and demonstration data shall be synthetic. |
| **BC-03** | SafeMed shall not present an AI-generated statement as a safety determination. AI output shall be visually and structurally separate from the sourced finding it explains. |

---

## 8. Requirements Traceability

### 8.1 Business → User → Functional

| BR | UR | FR |
|---|---|---|
| BR-01 | UR-01, UR-02, UR-04, UR-10 | FR-04…FR-12, FR-17…FR-20, FR-35 |
| BR-02 | UR-03 | FR-13…FR-16 |
| BR-03 | UR-05, UR-06, UR-07, UR-09 | FR-21…FR-34, FR-36 |
| BR-04 | UR-08 | FR-10, FR-14, FR-15 |
| BR-05 | — | BC-01, BC-03, AIR-01…AIR-05 |

### 8.2 Coverage summary

| Area | Requirements | Automated tests |
|---|---|---|
| Accounts and access | FR-01…FR-03 | 24 |
| Medication management | FR-04…FR-07 | 13 |
| Safety evaluation | FR-08…FR-12 | 30 |
| Recall monitoring | FR-13…FR-16 | 22 |
| Adherence | FR-17…FR-20 | 37 |
| Consent and caregiver access | FR-21…FR-27 | 37 |
| Audit | FR-28…FR-34 | 30 |
| AI boundary | AIR-01…AIR-05 | 15 |

**197 automated tests**, run on every push by `.github/workflows/ci.yml`.

---

## 9. Requirements Deliberately Not Met

Stated here rather than left to be discovered.

| Gap | Reason |
|---|---|
| No interface for reading the audit log | Records are written and queryable by SQL; no review screen was built. |
| Schedules stored as wall-clock UTC | Per-user time zones were descoped; the interface displays UTC rather than silently showing a wrong local time. |
| Single interaction dataset | DDInter only, so evaluation measures internal consistency rather than completeness. |
| Read-path audit failures tolerated | If an audit write fails, a caregiver's read is still served and the failure logged. A regulated system would refuse the read. See HANDBOOK §10.5. |
| Not deployed to a hosted environment | The system runs under Docker Compose; no production deployment was performed. |
| The `notifications` table is unused | The model and its channel/status enums were designed, but nothing writes a row and no email or SMS transport was integrated. Caregiver alerting is delivered by the caregiver dashboard instead, which satisfies UR-06 but leaves this table as dead schema. |
