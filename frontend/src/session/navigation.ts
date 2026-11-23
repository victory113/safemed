/**
 * Client-side navigation without adding a router dependency.
 *
 * The original route table read window.location once, which meant every link
 * was a full page reload - and after signing in, a reload would throw away the
 * session we had just put in memory. This keeps the same "read the path, pick
 * a page" idea but makes it reactive.
 *
 * pushState deliberately does not fire popstate (that event is for the back
 * button), so navigate() dispatches its own. That keeps one code path: every
 * path change, whether from a link or the back button, is handled identically.
 */
import { useEffect, useState } from "react";

const PATH_CHANGE = "safemed:navigate";

export function currentPath(): string {
  return window.location.pathname.replace(/\/+$/, "") || "/";
}

export function navigate(to: string): void {
  if (to === currentPath()) return;
  window.history.pushState({}, "", to);
  window.dispatchEvent(new Event(PATH_CHANGE));
}

export function usePath(): string {
  const [path, setPath] = useState(currentPath);

  useEffect(() => {
    const update = () => setPath(currentPath());
    window.addEventListener("popstate", update);
    window.addEventListener(PATH_CHANGE, update);
    return () => {
      window.removeEventListener("popstate", update);
      window.removeEventListener(PATH_CHANGE, update);
    };
  }, []);

  return path;
}
