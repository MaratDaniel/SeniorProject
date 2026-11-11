import { Icon } from "./Icons";

export type PillKind = "live" | "winning" | "outbid" | "offline" | "upcoming" | "closed" | "sold" | "no_sale" | "cancelled";

// Status is always a word plus an icon (or a word on its own for the plain, quiet states).
export function StatusPill({ kind }: { kind: PillKind }) {
  switch (kind) {
    case "live":
      return <span className="pill live"><Icon name="dot" />Live</span>;
    case "winning":
      return <span className="pill win"><Icon name="check" />Winning</span>;
    case "outbid":
      return <span className="pill out"><Icon name="down" />Outbid</span>;
    case "offline":
      return <span className="pill out"><Icon name="alert" />Offline</span>;
    case "upcoming":
      return <span className="pill plain"><Icon name="clock" />Upcoming</span>;
    case "sold":
      return <span className="pill win"><Icon name="check" />Closed</span>;
    case "closed":
      return <span className="pill plain"><Icon name="lock" />Closed</span>;
    case "no_sale":
      return <span className="pill plain"><Icon name="lock" />No sale</span>;
    case "cancelled":
      return <span className="pill plain"><Icon name="alert" />Cancelled</span>;
  }
}

export function EndingSoon() {
  return (
    <span className="ending">
      <Icon name="clock" />
      Ending soon
    </span>
  );
}
