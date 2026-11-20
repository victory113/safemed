import { useEffect } from "react";

import { CaregiverDashboard } from "./pages/caregiver/CaregiverDashboard";
import { Dashboard } from "./pages/dashboard/Dashboard";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { StyleGuide } from "./pages/StyleGuide";
import { navigate, usePath } from "./session/navigation";
import { useSession } from "./session/useSession";
import type { User } from "./api/types";

/**
 * The route table.
 *
 * Still small and dependency-free, but it reads the path reactively and knows
 * who is signed in, which it needs for three things:
 *
 *   - sending a signed-in person to their own home screen
 *   - keeping a signed-out person off both dashboards
 *   - keeping a caregiver out of the patient screens, and vice versa
 *
 * That last one is convenience, not security. The server decides what anyone
 * may actually read: a caregiver calling the patient endpoints gets their own
 * (empty) data, and the caregiver endpoints refuse anyone without an active
 * consent grant. Routing here simply avoids showing someone a screen that
 * would be blank for them.
 *
 * The redirect runs in an effect, not during render, because calling
 * navigate() while rendering would update history in the middle of React's
 * render pass. The guards below still refuse to render the protected page, so
 * nothing private appears in the frame before the redirect lands.
 */
function homeFor(user: User): string {
  return user.role === "CAREGIVER" ? "/caregiver" : "/dashboard";
}

export function Routes() {
  const path = usePath();
  const { user, loading } = useSession();

  const wantsPatient = path === "/dashboard";
  const wantsCaregiver = path === "/caregiver";
  const onAuthPage = path === "/" || path === "/login" || path === "/register";

  useEffect(() => {
    if (loading) return;

    if ((wantsPatient || wantsCaregiver) && !user) {
      navigate("/login");
      return;
    }
    if (!user) return;

    const home = homeFor(user);
    if (onAuthPage) navigate(home);
    // Signed in, but on the other role's screen.
    else if ((wantsPatient || wantsCaregiver) && path !== home) navigate(home);
  }, [loading, user, path, wantsPatient, wantsCaregiver, onAuthPage]);

  /* Still checking a stored token. Rendering either the login form or a
   * dashboard now would show the wrong one for a moment on every refresh. */
  if (loading) {
    return (
      <main className="app-container">
        <p role="status">Loading SafeMed...</p>
      </main>
    );
  }

  if (path === "/styleguide") return <StyleGuide />;

  /* Anyone who is not a caregiver gets the patient screen. Checking "is not a
   * caregiver" rather than "is a patient" matters: ADMIN is a third role in
   * the enum, and homeFor() sends it here, so an equality check would leave
   * an admin staring at a blank page with no way out. */
  if (wantsPatient) {
    return user && user.role !== "CAREGIVER" ? <Dashboard /> : null;
  }
  if (wantsCaregiver) return user?.role === "CAREGIVER" ? <CaregiverDashboard /> : null;

  if (path === "/register") return user ? null : <Register />;
  if (onAuthPage) return user ? null : <Login />;

  return (
    <main className="app-container">
      <h1>Page not found</h1>
      <a href={user ? homeFor(user) : "/login"}>
        {user ? "Go to your home screen" : "Go to log in"}
      </a>
    </main>
  );
}
