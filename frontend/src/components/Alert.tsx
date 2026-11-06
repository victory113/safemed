import type { ReactNode } from "react";
import "./components.css";

export type AlertLevel = "mild" | "moderate" | "severe" | "success";

interface AlertProps {
  level: AlertLevel;
  title: string;
  children?: ReactNode;
}

/* An icon per level, so meaning never depends on colour alone. Roughly 1 in
 * 12 men has some form of colour vision deficiency; a red box and an amber box
 * can look identical to them. The icon and the title text carry the meaning. */
const ICONS: Record<AlertLevel, string> = {
  mild: "i",
  moderate: "!",
  severe: "!!",
  success: "OK",
};

const LABELS: Record<AlertLevel, string> = {
  mild: "Information",
  moderate: "Warning",
  severe: "Important safety alert",
  success: "Success",
};

/**
 * A safety message.
 *
 * role="alert" on severe items makes a screen reader announce it as soon as it
 * appears. We deliberately do NOT use it for the other levels - if everything
 * interrupts, nothing does.
 */
export function Alert({ level, title, children }: AlertProps) {
  return (
    <div
      className={`sm-alert sm-alert--${level}`}
      role={level === "severe" ? "alert" : "status"}
    >
      <span className="sm-alert__icon" aria-hidden="true">
        {ICONS[level]}
      </span>
      <div className="sm-alert__body">
        <p className="sm-alert__title">
          <span className="sr-only">{LABELS[level]}: </span>
          {title}
        </p>
        {children && <div className="sm-alert__content">{children}</div>}
      </div>
    </div>
  );
}
