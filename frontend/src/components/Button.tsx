import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./components.css";

type Variant = "primary" | "secondary" | "danger";
type Size = "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  fullWidth?: boolean;
  children: ReactNode;
}

/**
 * The only button in the app.
 *
 * It extends ButtonHTMLAttributes, so every native prop (onClick, disabled,
 * type, aria-*) still works. We add styling choices on top rather than
 * reinventing a button - which keeps the built-in keyboard behaviour and
 * screen-reader semantics for free.
 */
export function Button({
  variant = "primary",
  size = "md",
  fullWidth = false,
  className = "",
  type = "button",
  children,
  ...rest
}: ButtonProps) {
  const classes = [
    "sm-button",
    `sm-button--${variant}`,
    size === "lg" ? "sm-button--lg" : "",
    fullWidth ? "sm-button--full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  // Defaulting type to "button" prevents the classic bug where a button
  // inside a form submits it by accident.
  return (
    <button type={type} className={classes} {...rest}>
      {children}
    </button>
  );
}
