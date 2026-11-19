import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateAuth } from '../src/pages/auth-validation.ts';
function form(values) {
  const data = new FormData();
  for (const [key, value] of Object.entries(values)) data.set(key, value);
  return data;
}
test('empty registration identifies every required field', () => {
  assert.deepEqual(Object.keys(validateAuth(form({}), true)), ['full_name', 'email', 'password']);
});
test('rejects whitespace names, malformed email, and short new passwords', () => {
  const errors = validateAuth(form({full_name: '  ', email: 'patient@', password: '1234567'}), true);
  assert.ok(errors.full_name && errors.email && errors.password);
});
test('accepts registration at the password minimum', () => {
  assert.deepEqual(validateAuth(form({full_name: 'Demo Patient', email: 'demo@example.com', password: '12345678'}), true), {});
});
test('login does not impose registration name or password length rules', () => {
  assert.deepEqual(validateAuth(form({email: 'demo@example.com', password: 'short'}), false), {});
});
test('login rejects a missing password', () => {
  assert.deepEqual(Object.keys(validateAuth(form({email: 'demo@example.com'}), false)), ['password']);
});
