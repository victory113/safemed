import { useEffect } from "react";

import { Dashboard } from "./pages/dashboard/Dashboard";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { StyleGuide } from "./pages/StyleGuide";
import { navigate, usePath } from "./session/navigation";
import { useSession } from "./session/useSession";

/**
 * The route table.
 *
 * Still small and dependency-free, but it now reads the path reactively and
 * knows who is signed in, which it needs for two things:
 *
 *   - sending a signed-in person to the dashboard rather than the login form
 *   - keeping a signed-out person off the dashboard
 *
 * The redirect runs in an effect, not during render, because calling
 * navigate() while rendering would update history in the middle of React's
 * render pass. The guards below still refuse to render the protected page, so
 * nothing private appears in the frame before the redirect lands.
 */
export function Routes() {
  const path = usePath();
  const { user, loading } = useSession();

  const wantsDashboard = path === "/dashboard";
  const onAuthPage = path === "/" || path === "/login" || path === "/register";

  useEffect(() => {
    if (loading) return;
    if (wantsDashboard && !user) navigate("/login");
    if (onAuthPage && user) navigate("/dashboard");
  }, [loading, user, wantsDashboard, onAuthPage]);

  /* Still checking a stored token. Rendering either the login form or the
   * dashboard now would show the wrong one for a moment on every refresh. */
  if (loading) {
    return (
      <main className="app-container">
        <p role="status">Loading SafeMed...</p>
      </main>
    );
  }

  if (path === "/styleguide") return <StyleGuide />;

  if (wantsDashboard) {
    return user ? <Dashboard /> : null;
  }

  if (path === "/register") return user ? null : <Register />;
  if (onAuthPage) return user ? null : <Login />;

  return (
    <main className="app-container">
      <h1>Page not found</h1>
      <a href={user ? "/dashboard" : "/login"}>
        {user ? "Go to your dashboard" : "Go to log in"}
      </a>
    </main>
  );
}
