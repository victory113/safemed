/**
 * The patient's home screen.
 *
 * Order on the page is a safety decision, not a layout one. Safety findings
 * come first, because a serious interaction is the most important thing
 * SafeMed has to say. The daily check-in comes next, because it is what a
 * patient opens the app to do. Adherence and the medication list follow.
 */
import { useSession } from "../../session/useSession";
import { AdherenceSummary } from "./AdherenceSummary";
import { Medications } from "./Medications";
import { SafetyFindings } from "./SafetyFindings";
import { TodayDoses } from "./TodayDoses";
import { useDashboard } from "./useDashboard";
import "./dashboard.css";

export function Dashboard() {
  const { user, logOut } = useSession();
  const { doses, adherence, findings, medications, loading, error, reload } =
    useDashboard();

  /* A patient's first name is enough, and friendlier than the full name. */
  const firstName = user?.full_name?.split(" ")[0] ?? "";

  return (
    <div className="dash">
      <a className="sr-only dash-skip" href="#dash-main">
        Skip to content
      </a>

      <header className="dash-header">
        <div className="dash-header__brand">
          <span className="dash-header__mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path
                d="M16 3 27 7v8c0 7-11 14-11 14S5 22 5 15V7l11-4Z"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="M16 10v12m-6-6h12"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span className="dash-header__name">SafeMed</span>
        </div>

        <div className="dash-header__account">
          {user && (
            <span className="dash-header__who">
              {user.full_name}
              <span className="dash-header__role">
                {user.role === "CAREGIVER" ? "Caregiver" : "Patient"}
              </span>
            </span>
          )}
          <button type="button" className="dash-header__out" onClick={logOut}>
            Log out
          </button>
        </div>
      </header>

      <main id="dash-main" className="dash-main">
        <div className="dash-greeting">
          <h1>{firstName ? `Hello, ${firstName}.` : "Hello."}</h1>
          <p>Here is where things stand today.</p>
        </div>

        {/* A failed load is reported in place. The alternative - an empty
            dashboard with no explanation - would read as "nothing is wrong",
            which is the one thing a safety screen must never imply when it
            does not actually know. */}
        {error && (
          <div className="dash-error" role="alert">
            <p className="dash-error__title">We could not load your information</p>
            <p>{error}</p>
            <button type="button" onClick={() => void reload()}>
              Try again
            </button>
          </div>
        )}

        {loading ? (
          <p className="dash-loading" role="status">
            Loading your information...
          </p>
        ) : (
          !error && (
            <div className="dash-grid">
              <div className="dash-col dash-col--main">
                <SafetyFindings findings={findings} onChange={reload} />
                <TodayDoses doses={doses} onChange={reload} />
              </div>
              <div className="dash-col dash-col--side">
                <AdherenceSummary adherence={adherence} />
                <Medications medications={medications} onChange={reload} />
              </div>
            </div>
          )
        )}
      </main>

      <footer className="dash-footer">
        <span>SafeMed</span>
        <span>
          Not a medical device. Does not diagnose or prescribe. Always speak to
          your doctor or pharmacist.
        </span>
      </footer>
    </div>
  );
}
