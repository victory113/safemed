/**
 * The only place in the frontend that talks to the API.
 *
 * Everything goes through `request`, which means token handling, error
 * shaping and the base URL exist once rather than in every component. If we
 * later move the token out of localStorage, this is the only file that changes.
 */
import type {
  Adherence,
  CaregiverPatient,
  ConsentGrant,
  Dose,
  Finding,
  Medication,
  MedicationCreate,
  Token,
  User,
} from "./types";

/* Vite replaces import.meta.env at build time. The fallback is the port
 * docker-compose maps the API to, so a fresh clone works with no .env file. */
const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const API = `${BASE_URL}/api/v1`;

const TOKEN_KEY = "safemed.token";

/* localStorage throws in some private-browsing modes rather than returning
 * null, so every access is guarded. A storage failure must log the user out,
 * not crash the page. */
export function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function writeToken(token: string | null): void {
  try {
    if (token === null) window.localStorage.removeItem(TOKEN_KEY);
    else window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* Nothing useful to do. The session simply will not survive a reload. */
  }
}

/**
 * An API error with the status code kept intact.
 *
 * The status matters to callers: 409 on confirming a dose means "someone
 * already logged this", which is worth a different message than a real
 * failure. Throwing a plain Error would lose that.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** FastAPI puts validation errors in a list under `detail`. Flatten to a
 *  sentence rather than showing a patient a JSON array. */
function readDetail(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null) return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        typeof item === "object" && item !== null
          ? String((item as { msg?: unknown }).msg ?? "")
          : "",
      )
      .filter(Boolean);
    if (messages.length) return messages.join(". ");
  }
  return fallback;
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = readToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    /* fetch only rejects on a network-level failure, so this is genuinely
     * "the API is unreachable" rather than any HTTP error. Status 0 marks it
     * as such. */
    throw new ApiError(0, "Could not reach SafeMed. Is the API running?");
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      readDetail(parsed, `Request failed (${response.status})`),
    );
  }
  return parsed as T;
}

export const api = {
  /* ---- auth ---- */
  register: (body: {
    email: string;
    password: string;
    full_name: string;
    role: string;
  }) => request<User>("/auth/register", { method: "POST", body, auth: false }),

  login: (body: { email: string; password: string }) =>
    request<Token>("/auth/login", { method: "POST", body, auth: false }),

  me: () => request<User>("/auth/me"),

  /* ---- medications ---- */
  listMedications: (status: "ACTIVE" | "ALL" = "ACTIVE") =>
    request<Medication[]>(`/medications?status=${status}`),

  addMedication: (body: MedicationCreate) =>
    request<Medication>("/medications", { method: "POST", body }),

  stopMedication: (id: string) =>
    request<Medication>(`/medications/${id}`, { method: "DELETE" }),

  /* ---- doses ---- */
  dosesToday: () => request<Dose[]>("/doses/today"),

  doseHistory: (days = 7) => request<Dose[]>(`/doses/history?days=${days}`),

  adherence: (days = 7) => request<Adherence>(`/doses/adherence?days=${days}`),

  confirmDose: (id: string) =>
    request<Dose>(`/doses/${id}/confirm`, { method: "POST" }),

  skipDose: (id: string, note?: string) =>
    request<Dose>(`/doses/${id}/skip`, {
      method: "POST",
      body: { note: note ?? null },
    }),

  /* ---- findings ---- */
  listFindings: () => request<Finding[]>("/findings"),

  reEvaluate: () => request<Finding[]>("/findings/re-evaluate", { method: "POST" }),

  acknowledgeFinding: (id: string) =>
    request<Finding>(`/findings/${id}/acknowledge`, { method: "POST" }),
};

/**
 * Consent and the caregiver views.
 *
 * Kept as a separate object so it is obvious at the call site which requests
 * cross a consent boundary. Every `caregiverX` call below is refused with a
 * 403 unless the signed-in caregiver holds an ACTIVE grant for that patient,
 * checked by the server on every request.
 */
export const consentApi = {
  listGrants: (status?: "PENDING" | "ACTIVE" | "REVOKED") =>
    request<ConsentGrant[]>(`/consent${status ? `?status=${status}` : ""}`),

  invite: (caregiverEmail: string) =>
    request<ConsentGrant>("/consent/invitations", {
      method: "POST",
      body: { caregiver_email: caregiverEmail },
    }),

  accept: (grantId: string) =>
    request<ConsentGrant>(`/consent/${grantId}/accept`, { method: "POST" }),

  revoke: (grantId: string) =>
    request<ConsentGrant>(`/consent/${grantId}/revoke`, { method: "POST" }),

  myPatients: () => request<CaregiverPatient[]>("/caregiver/patients"),

  patientFindings: (patientId: string) =>
    request<Finding[]>(`/caregiver/patients/${patientId}/findings`),

  patientDosesToday: (patientId: string) =>
    request<Dose[]>(`/caregiver/patients/${patientId}/doses/today`),

  patientAdherence: (patientId: string, days = 7) =>
    request<Adherence>(`/caregiver/patients/${patientId}/adherence?days=${days}`),

  patientMedications: (patientId: string) =>
    request<Medication[]>(`/caregiver/patients/${patientId}/medications`),
};
