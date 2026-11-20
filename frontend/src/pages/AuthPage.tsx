import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Button, Input } from '../components';
import './auth.css';
import { validateAuth } from './auth-validation';
import type { AuthField } from './auth-validation';
import { Link } from '../session/Link';
import { navigate } from '../session/navigation';
import { errorMessage } from '../session/errors';
import { useSession } from '../session/useSession';

/** Shared layout keeps login and registration consistent; wrappers choose the mode. */
export function AuthPage({ register = false }: { register?: boolean }) {
  const { logIn, signUp } = useSession();
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<AuthField, string>>>({});
  // An error from the API, as opposed to a field that failed local validation.
  const [apiError, setApiError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  /**
   * Validate locally first, then talk to the API.
   *
   * Local validation stays because it gives instant, per-field messages. The
   * server is still the authority - it decides whether the email is taken and
   * whether the password is right - so a server error is shown as its own
   * message rather than being attached to a guessed field.
   */
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);

    const next = validateAuth(data, register);
    setErrors(next);
    setApiError(null);

    // Focus the first invalid field so keyboard and screen-reader users can fix it.
    const first = Object.keys(next)[0];
    if (first) {
      formRef.current?.querySelector<HTMLInputElement>(`[name="${first}"]`)?.focus();
      return;
    }

    const email = String(data.get('email') ?? '').trim();
    const password = String(data.get('password') ?? '');

    setPending(true);
    try {
      if (register) {
        await signUp(
          String(data.get('full_name') ?? '').trim(),
          email,
          password,
          String(data.get('role') ?? 'PATIENT'),
        );
      } else {
        await logIn(email, password);
      }
      navigate('/dashboard');
    } catch (caught) {
      setApiError(errorMessage(caught));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="auth-shell">
      <a className="sr-only auth-skip" href="#auth-form">Skip to form</a>
      <header className="auth-brand" aria-label="SafeMed">
        <span className="auth-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M16 3 27 7v8c0 7-11 14-11 14S5 22 5 15V7l11-4Z" stroke="currentColor" strokeWidth="2"/><path d="M16 10v12m-6-6h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg></span>
        <span>SafeMed<span className="auth-brand-dot">.</span></span>
      </header>
      <main className="auth-main">
        <section className="auth-card" aria-labelledby="auth-title">
          <div className="auth-intro">
            <span className="auth-eyebrow">A LITTLE CARE, EVERY DAY</span>
            <h1 id="auth-title">{register ? 'Start with peace of mind.' : 'Welcome back.'}</h1>
            <p>{register ? 'A simpler way to keep track of medications. For you, or someone you care for.' : 'Your medications, your routine.\nA little easier to keep track of.'}</p>
          </div>
          <nav className="auth-tabs" aria-label="Account access">
            <Link to="/login" aria-current={!register ? 'page' : undefined}>Log in</Link>
            <Link to="/register" aria-current={register ? 'page' : undefined}>Create account</Link>
          </nav>
          {/* noValidate lets us display consistent, field-specific messages. */}
          <form id="auth-form" ref={formRef} onSubmit={submit} onChange={() => setApiError(null)} noValidate>
            {register && <Input label="Full name" name="full_name" autoComplete="name" required error={errors.full_name} placeholder="Your full name" />}
            <Input label="Email address" name="email" type="email" autoComplete="email" autoCapitalize="none" spellCheck={false} required error={errors.email} placeholder="you@example.com" />
            {/* A separate type="button" prevents Show/Hide from submitting the form. */}
            <div className="auth-password">
              <Input label="Password" id="auth-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} required hint={register ? 'Use at least 8 characters.' : undefined} error={errors.password} />
              <button className="auth-show" type="button" aria-controls="auth-password" aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? 'Hide' : 'Show'}</button>
            </div>
            {register && <fieldset className="auth-role"><legend>I’m here as a</legend><div><label><input type="radio" name="role" value="PATIENT" defaultChecked /> Patient</label><label><input type="radio" name="role" value="CAREGIVER" /> Caregiver</label></div></fieldset>}
            <Button type="submit" size="lg" fullWidth disabled={pending}>
              {pending
                ? register ? 'Creating your account...' : 'Signing you in...'
                : <>{register ? 'Create account' : 'Log in'}<span aria-hidden="true"> →</span></>}
            </Button>
            {/* role="alert" so a screen reader announces a failed sign-in
                immediately. The message is whatever the API said - we never
                guess which field was wrong, because on login the server
                deliberately does not tell us. */}
            {apiError && <p className="auth-feedback auth-feedback--error" role="alert">{apiError}</p>}
          </form>
          <p className="auth-switch">{register ? 'Already have an account?' : 'New to SafeMed?'} <Link to={register ? '/login' : '/register'}>{register ? 'Log in' : 'Create an account'}</Link></p>
        </section>
        <p className="auth-care-note"><span aria-hidden="true">♡</span> A little support for your everyday care.</p>
      </main>
      <footer className="auth-footer"><span>SafeMed</span><span>Made for everyday peace of mind.</span></footer>
    </div>
  );
}
