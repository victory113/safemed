/**
 * The shapes the API sends and accepts.
 *
 * These mirror the Pydantic schemas in backend/app/schemas/ exactly. They are
 * written by hand rather than generated, so the rule is: change a schema on
 * the backend, change it here in the same commit. The string unions below are
 * copied from backend/app/models/enums.py.
 *
 * Every field the backend declares as nullable is nullable here too. That is
 * the whole point of writing them out - `ai_explanation: string | null` forces
 * the UI to handle a finding whose AI explanation never arrived, instead of
 * rendering "undefined" to a patient.
 */

export type UserRole = "PATIENT" | "CAREGIVER" | "ADMIN";
export type MedicationStatus = "ACTIVE" | "STOPPED";
export type Frequency = "DAILY" | "WEEKLY";
export type DoseStatus = "SCHEDULED" | "DUE" | "TAKEN" | "MISSED" | "SKIPPED";
export type FindingType = "INTERACTION" | "RECALL" | "DUPLICATE_THERAPY";
export type Severity = "MILD" | "MODERATE" | "SEVERE";
export type FindingStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
export type RecallMatch = "CONFIRMED" | "POSSIBLE";
export type ConsentStatus = "PENDING" | "ACTIVE" | "REVOKED";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Medication {
  id: string;
  name_entered: string;
  /** What RxNorm matched it to. Null when RxNorm could not resolve the name. */
  normalized_name: string | null;
  /** RxNorm concept id. Null means interaction checks fall back to the name. */
  rxcui: string | null;
  ndc: string | null;
  dose_amount: string | null;
  dose_unit: string | null;
  notes: string | null;
  status: MedicationStatus;
  started_on: string | null;
  stopped_on: string | null;
  created_at: string;
}

export interface MedicationCreate {
  name_entered: string;
  dose_amount?: string | null;
  dose_unit?: string | null;
  ndc?: string | null;
  notes?: string | null;
  /** "HH:MM" times of day. Each becomes a dose schedule to log against. */
  times?: string[];
  grace_minutes?: number;
}

export interface DoseSchedule {
  id: string;
  time_of_day: string;
  frequency: Frequency;
  days_of_week: string | null;
  grace_minutes: number;
  is_active: boolean;
}

export interface Dose {
  id: string;
  medication_id: string;
  medication_name: string;
  dose_amount: string | null;
  dose_unit: string | null;
  /** ISO timestamp, UTC. */
  scheduled_for: string;
  status: DoseStatus;
  confirmed_at: string | null;
}

export interface Adherence {
  days: number;
  taken: number;
  missed: number;
  skipped: number;
  scheduled: number;
  resolved: number;
  /** Null when nothing has resolved yet. Null is NOT zero - see the backend
   *  schema. The UI must say "no data yet" rather than "0%". */
  rate: number | null;
}

export interface FindingMedication {
  id: string;
  name: string;
}

export interface Finding {
  id: string;
  finding_type: FindingType;
  severity: Severity;
  status: FindingStatus;
  title: string;
  /** Always present. Written by the deterministic engine, never by AI. */
  detail: string;
  source_name: string;
  source_version: string | null;
  recall_match: RecallMatch | null;
  /** Plain-language rewrite. Null when the AI layer is disabled, unavailable,
   *  or its output failed the guardrail check. `detail` is the fallback. */
  ai_explanation: string | null;
  detected_at: string;
  acknowledged_at: string | null;
  medications: FindingMedication[];
}
