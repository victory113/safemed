const baseUrl = (import.meta.env?.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/+$/, '');
const tokenKey = 'safemed.accessToken';

export function setAccessToken(token: string | null) {
  if (token === null) {
    sessionStorage.removeItem(tokenKey);
  } else {
    sessionStorage.setItem(tokenKey, token);
  }
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = sessionStorage.getItem(tokenKey);
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...options, headers });
  } catch {
    throw new Error('Could not reach SafeMed. Check your connection and try again.');
  }

  if (response.status === 401 && path !== '/auth/login' && path !== '/auth/register') {
    // An older request must not clear a session established while it was in flight.
    if (sessionStorage.getItem(tokenKey) === token) {
      setAccessToken(null);
      if (window.location.pathname !== '/login') window.location.assign('/login');
    }
    throw new Error('Your session has expired. Please log in again.');
  }

  if (!response.ok) {
    if (response.status >= 500) {
      throw new Error('SafeMed is temporarily unavailable. Please try again.');
    }
    const error = await response.json().catch(() => null);
    if (typeof error?.detail === 'string') throw new Error(error.detail);
    if (response.status === 422) throw new Error('Check the information you entered and try again.');
    throw new Error('SafeMed could not complete your request. Please try again.');
  }

  if (response.status === 204) return undefined as T;
  return response.json().catch(() => {
    throw new Error('SafeMed returned an unexpected response. Please try again.');
  });
}
