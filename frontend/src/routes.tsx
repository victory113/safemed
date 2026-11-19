import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { StyleGuide } from './pages/StyleGuide';

// Small route table without a new dependency. Ordinary links use Vite’s SPA fallback.
// Keep the shared component reference accessible separately from the account pages.
export function Routes() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  if (path === '/styleguide') return <StyleGuide />;
  if (path === '/register') return <Register />;
  if (path === '/' || path === '/login') return <Login />;
  return <main className="app-container"><h1>Page not found</h1><a href="/login">Go to log in</a></main>;
}
