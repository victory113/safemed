import type { ReactNode } from "react";
import "./components.css";

type Tone = "mild" | "moderate" | "severe" | "success" | "neutral";

interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
}

/**
 * A small status pill - dose status, finding severity, consent state.
 *
 * The text inside always states the status in words. The colour is a visual
 * shortcut, never the only signal.
 */
export function Badge({ tone = "neutral", children }: BadgeProps) {
  return <span className={`sm-badge sm-badge--${tone}`}>{children}</span>;
}
