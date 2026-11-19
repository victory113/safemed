import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import './welcome.css';

const SEEN_KEY = 'safemed-welcome-seen';
// Session storage avoids replaying the intro when users switch between forms.
// Reduced-motion users go straight to the page. Storage failure never blocks access.
function shouldWelcome() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  try { return sessionStorage.getItem(SEEN_KEY) !== 'yes'; }
  catch { return true; }
}

/** A brief introduction once per tab session; never waits on network requests. */
export function Welcome({ children }: { children: ReactNode }) {
  const [visible, setVisible] = useState(shouldWelcome);
  useEffect(() => {
    if (!visible) return;
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    function finish() {
      try { sessionStorage.setItem(SEEN_KEY, 'yes'); } catch { /* Storage may be unavailable. */ }
      setVisible(false);
    }
    // Matches the fade-in, pause, and fade-out durations in welcome.css.
    const timer = window.setTimeout(finish, 1400);
    function onPreferenceChange() { if (preference.matches) finish(); }
    preference.addEventListener('change', onPreferenceChange);
    // Cleanup also prevents duplicate timers during React StrictMode development.
    return () => {
      window.clearTimeout(timer);
      preference.removeEventListener('change', onPreferenceChange);
    };
  }, [visible]);

  return <>
    {visible && <div className="welcome" role="status" aria-label="Welcome to SafeMed">
      <div className="welcome-brand" aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none"><path d="M16 3 27 7v8c0 7-11 14-11 14S5 22 5 15V7l11-4Z" stroke="currentColor" strokeWidth="2"/><path d="M16 10v12m-6-6h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
        <span>SafeMed<span className="welcome-dot">.</span></span>
      </div>
    </div>}
    {/* Keep the hidden form out of the tab order until the intro finishes. */}
    <div className={visible ? 'welcome-content welcome-content--waiting' : 'welcome-content'} inert={visible} aria-hidden={visible || undefined}>{children}</div>
  </>;
}
