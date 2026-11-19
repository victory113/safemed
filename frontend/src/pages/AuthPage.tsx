import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Button, Input } from '../components';
import './auth.css';
import { validateAuth } from './auth-validation';
import type { AuthField } from './auth-validation';

/** Shared layout keeps login and registration consistent; wrappers choose the mode. */
export function AuthPage({ register = false }: { register?: boolean }) {
  // These states affect presentation only. Credentials are never stored or sent.
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Partial<Record<AuthField, string>>>({});
  const [submitted, setSubmitted] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  // Keep the user on the page and validate before showing the demo response.
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const next = validateAuth(data, register);
    setErrors(next);
    setSubmitted(false);
    // Focus the first invalid field so keyboard and screen-reader users can fix it.
    const first = Object.keys(next)[0];
    if (first) formRef.current?.querySelector<HTMLInputElement>(`[name="${first}"]`)?.focus();
    else setSubmitted(true);
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
            <a href="/login" aria-current={!register ? 'page' : undefined}>Log in</a>
            <a href="/register" aria-current={register ? 'page' : undefined}>Create account</a>
          </nav>
          {/* noValidate lets us display consistent, field-specific messages. */}
          <form id="auth-form" ref={formRef} onSubmit={submit} onChange={() => setSubmitted(false)} noValidate>
            {register && <Input label="Full name" name="full_name" autoComplete="name" required error={errors.full_name} placeholder="Your full name" />}
            <Input label="Email address" name="email" type="email" autoComplete="email" autoCapitalize="none" spellCheck={false} required error={errors.email} placeholder="you@example.com" />
            {/* A separate type="button" prevents Show/Hide from submitting the form. */}
            <div className="auth-password">
              <Input label="Password" id="auth-password" name="password" type={showPassword ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} required hint={register ? 'Use at least 8 characters.' : undefined} error={errors.password} />
              <button className="auth-show" type="button" aria-controls="auth-password" aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? 'Hide' : 'Show'}</button>
            </div>
            {register && <fieldset className="auth-role"><legend>I’m here as a</legend><div><label><input type="radio" name="role" value="PATIENT" defaultChecked /> Patient</label><label><input type="radio" name="role" value="CAREGIVER" /> Caregiver</label></div></fieldset>}
            <Button type="submit" size="lg" fullWidth>{register ? 'Create account' : 'Log in'}<span aria-hidden="true"> →</span></Button>
            {/* Replace this demo state with the API result when auth is integrated. */}
            {submitted && <p className="auth-feedback" role="status">{register ? 'Your form is ready. This preview does not create an account yet.' : 'Your form is ready. This preview does not sign you in yet.'}</p>}
          </form>
          <p className="auth-switch">{register ? 'Already have an account?' : 'New to SafeMed?'} <a href={register ? '/login' : '/register'}>{register ? 'Log in' : 'Create an account'}</a></p>
        </section>
        <p className="auth-care-note"><span aria-hidden="true">♡</span> A little support for your everyday care.</p>
      </main>
      <footer className="auth-footer"><span>SafeMed</span><span>Made for everyday peace of mind.</span></footer>
    </div>
  );
}
