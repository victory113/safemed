import type { ReactNode } from "react";
import "./components.css";

interface CardProps {
  title?: string;
  /** Rendered on the right of the header - a badge or a small action. */
  action?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
}

/**
 * A titled container. Used for every grouped block of content so that
 * spacing and borders stay identical across the app.
 *
 * The title renders as <h2>, which keeps the page's heading order sensible
 * for screen-reader users navigating by headings.
 */
export function Card({ title, action, footer, children }: CardProps) {
  return (
    <section className="sm-card">
      {(title || action) && (
        <header className="sm-card__header">
          {title && <h2 className="sm-card__title">{title}</h2>}
          {action}
        </header>
      )}
      <div>{children}</div>
      {footer && <div className="sm-card__footer">{footer}</div>}
    </section>
  );
}
