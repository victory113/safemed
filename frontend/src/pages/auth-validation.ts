export type AuthField = 'full_name' | 'email' | 'password';
/** Pure validation is shared by the form and tests. Backend validation is still required. */
export function validateAuth(data: FormData, register: boolean) {
  const errors: Partial<Record<AuthField, string>> = {};
  if (register && !String(data.get('full_name') ?? '').trim()) errors.full_name = 'Enter your full name.';
  const email = String(data.get('email') ?? '').trim();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = 'Enter a valid email address.';
  // Do not trim passwords: spaces may be intentional. Enforce length only on signup.
  const password = String(data.get('password') ?? '');
  if (!password) errors.password = 'Enter your password.';
  else if (register && password.length < 8) errors.password = 'Use at least 8 characters.';
  return errors;
}
