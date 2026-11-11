import { Link } from "react-router";
import type { AuctionCard } from "../api/types";
import { phaseOf, displayPrice } from "../lib/auction";
import { countdown, dateLong, ENDING_SOON_MS, formatName, money } from "../lib/format";
import { Icon, Mark } from "./Icons";
import { EndingSoon, StatusPill } from "./StatusPill";

export function NoPhoto() {
  return (
    <div className="nophoto">
      <Mark />
      <span>No photo yet</span>
    </div>
  );
}

function bidsText(n: number): string {
  return n === 1 ? "1 bid" : `${n} bids`;
}

type Variant = "grid" | "big" | "side";

export function LotCard({ card, now, variant = "grid" }: { card: AuctionCard; now: number; variant?: Variant }) {
  const phase = phaseOf(card, now);
  const remaining = Date.parse(card.ends_at) - now;
  const ending = phase === "live" && remaining <= ENDING_SOON_MS;
  const Heading = variant === "grid" ? "h2" : "h3";

  let pill;
  if (phase === "live") pill = ending ? <EndingSoon /> : <StatusPill kind="live" />;
  else if (phase === "upcoming") pill = <StatusPill kind="upcoming" />;
  else if (phase === "cancelled") pill = <StatusPill kind="cancelled" />;
  else if (phase === "closing") pill = <span className="pill plain"><Icon name="clock" />Closing</span>;
  else pill = card.status === "no_sale" ? <StatusPill kind="no_sale" /> : <StatusPill kind="closed" />;

  let price;
  let note: string | null = null;
  if (phase === "live" || phase === "closing") {
    price = (
      <div className="price">
        <b>{money(displayPrice(card))}</b>
        <span>{card.current_price ? "Current price" : "Starting price"}</span>
        {phase === "live" && (ending || variant === "big") ? (
          <span className={ending ? "ending" : "ends-in"}>
            <Icon name="clock" />
            Ends in {countdown(remaining)}
          </span>
        ) : null}
      </div>
    );
    note =
      phase === "live"
        ? `Closes ${dateLong(card.ends_at)} · ${bidsText(card.bid_count)}`
        : `The closing time has passed · ${bidsText(card.bid_count)}`;
  } else if (phase === "upcoming") {
    price = (
      <div className="price">
        <span>Opens {dateLong(card.starts_at)}</span>
      </div>
    );
    note = `Starting price ${money(card.starting_price)} · Closes ${dateLong(card.ends_at)}`;
  } else if (phase === "cancelled") {
    price = (
      <div className="price">
        <span>Withdrawn by the seller</span>
      </div>
    );
  } else if (card.status === "closed") {
    price = (
      <div className="price">
        <b>{money(displayPrice(card))}</b>
        <span>Sold</span>
      </div>
    );
    note = `Closed ${dateLong(card.ends_at)} · ${bidsText(card.bid_count)}`;
  } else {
    price = (
      <div className="price">
        {card.current_price ? <b>{money(card.current_price)}</b> : null}
        <span>No sale</span>
      </div>
    );
    note = card.bid_count === 0 ? "Nobody placed a bid" : "The reserve price was not met";
  }

  return (
    <Link className={`lot${variant === "big" ? " big" : ""}`} to={`/auctions/${card.id}`}>
      <div className="ph">
        {card.cover_url ? <img src={card.cover_url} alt={`Photo of ${card.title}`} loading="lazy" /> : <NoPhoto />}
      </div>
      <div className="top">
        {pill}
        <span className="fmt">
          {formatName(card.format)}
          {variant === "grid" ? "" : " auction"}
        </span>
      </div>
      <Heading>{card.title}</Heading>
      {price}
      {note ? <p className="note">{note}</p> : null}
    </Link>
  );
}
