import { useId } from "react";
import type { InputHTMLAttributes } from "react";
import "./components.css";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Always required. A placeholder is not a label. */
  label: string;
  hint?: string;
  error?: string;
}

/**
 * A labelled text input.
 *
 * Three accessibility details that are easy to get wrong:
 *
 * 1. useId() generates a unique id, so htmlFor and id always match even when
 *    the same field appears twice on a page. Clicking the label then focuses
 *    the input, which also gives a much larger tap target.
 * 2. aria-describedby points at the hint and error text, so a screen reader
 *    announces them with the field instead of leaving them orphaned.
 * 3. aria-invalid marks the field as failing validation. Our CSS colours the
 *    border from that attribute, so the visual and the announced state can
 *    never disagree.
 */
export function Input({ label, hint, error, required, id, ...rest }: InputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="sm-field">
      <label className="sm-field__label" htmlFor={inputId}>
        {label}
        {required && (
          <span className="sm-field__required" aria-hidden="true">
            *
          </span>
        )}
        {required && <span className="sr-only"> (required)</span>}
      </label>

      <input
        id={inputId}
        className="sm-field__input"
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      />

      {hint && (
        <span className="sm-field__hint" id={hintId}>
          {hint}
        </span>
      )}
      {error && (
        <span className="sm-field__error" id={errorId}>
          {error}
        </span>
      )}
    </div>
  );
}
