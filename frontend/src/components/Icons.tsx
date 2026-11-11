import type { CSSProperties } from "react";

// SVG sprite from the design handoff. Rendered once at the root; icons reference it by id.

export type IconName =
  | "check"
  | "down"
  | "clock"
  | "alert"
  | "info"
  | "lock"
  | "arrow"
  | "upload"
  | "dot"
  | "plus"
  | "eye"
  | "search"
  | "mail";

export function SpriteDefs() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true" focusable="false">
      <defs>
        <symbol id="mark" viewBox="0 0 190 150">
          <circle cx="45" cy="37" r="32" fill="currentColor" />
          <circle cx="148" cy="37" r="32" fill="currentColor" />
          <rect x="2" y="69" width="189" height="20" rx="10" fill="currentColor" />
          <path d="M96 97 68 149h57z" fill="currentColor" />
          <circle cx="96" cy="78" r="18" style={{ fill: "var(--mark-dot,#85601C)" }} />
        </symbol>
        <symbol id="i-check" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" /></symbol>
        <symbol id="i-down" viewBox="0 0 24 24"><path d="M12 5v14M6 13l6 6 6-6" /></symbol>
        <symbol id="i-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></symbol>
        <symbol id="i-alert" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.01" /></symbol>
        <symbol id="i-info" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.01" /></symbol>
        <symbol id="i-lock" viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></symbol>
        <symbol id="i-arrow" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6" /></symbol>
        <symbol id="i-upload" viewBox="0 0 24 24"><path d="M12 16V5M7 10l5-5 5 5M5 19h14" /></symbol>
        <symbol id="i-dot" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" style={{ fill: "currentColor" }} /></symbol>
        <symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></symbol>
        <symbol id="i-eye" viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></symbol>
        <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></symbol>
        <symbol id="i-mail" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></symbol>
      </defs>
    </svg>
  );
}

export function Icon({ name, style }: { name: IconName; style?: CSSProperties }) {
  return (
    <svg className="icon" aria-hidden="true" style={style}>
      <use href={`#i-${name}`} />
    </svg>
  );
}

export function Mark({ style }: { style?: CSSProperties }) {
  return (
    <svg aria-hidden="true" style={style}>
      <use href="#mark" />
    </svg>
  );
}
