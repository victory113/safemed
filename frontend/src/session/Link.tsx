import type { AnchorHTMLAttributes, ReactNode } from "react";

import { navigate } from "./navigation";

/**
 * An anchor that navigates without reloading the page.
 *
 * It stays a real `<a>` with a real href, so middle-click, ctrl-click and
 * "open in new tab" all keep working, and a screen reader still announces it
 * as a link. Only a plain left-click is intercepted - which is also why the
 * modifier keys are checked before calling preventDefault.
 */
export function Link({
  to,
  children,
  ...rest
}: { to: string; children: ReactNode } & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a
      href={to}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
        event.preventDefault();
        navigate(to);
      }}
      {...rest}
    >
      {children}
    </a>
  );
}
