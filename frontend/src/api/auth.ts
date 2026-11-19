import { apiRequest, setAccessToken } from './client';

type AccountRole = 'PATIENT' | 'CAREGIVER';

interface LoginRequest {
  email: string;
  password: string;
}

interface RegisterRequest extends LoginRequest {
  full_name: string;
  role: AccountRole;
}

interface User {
  id: string;
  email: string;
  full_name: string;
  role: AccountRole | 'ADMIN';
  is_active: boolean;
}

interface AuthToken {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export function registerAccount(account: RegisterRequest) {
  return apiRequest<User>('/auth/register', { method: 'POST', body: JSON.stringify(account) });
}

export async function signIn(credentials: LoginRequest) {
  const token = await apiRequest<AuthToken>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  });
  setAccessToken(token.access_token);
  try {
    return await apiRequest<User>('/auth/me');
  } catch (error) {
    setAccessToken(null);
    throw error;
  }
}
