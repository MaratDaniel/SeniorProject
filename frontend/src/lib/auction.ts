import type { AuctionCard, AuctionStatus } from "../api/types";

export type Phase = "upcoming" | "live" | "closing" | "ended" | "cancelled";

/**
 * Where an auction stands right now. The server decides; this only mirrors it for display,
 * using server time. "closing" covers the moment between the closing time and the server's close.
 */
export function phaseOf(a: { status: AuctionStatus; starts_at: string; ends_at: string }, now: number): Phase {
  if (a.status === "cancelled") return "cancelled";
  if (a.status === "closed" || a.status === "no_sale") return "ended";
  if (now < Date.parse(a.starts_at)) return "upcoming";
  if (now >= Date.parse(a.ends_at)) return "closing";
  return "live";
}

export function displayPrice(card: Pick<AuctionCard, "current_price" | "starting_price">): string {
  return card.current_price ?? card.starting_price;
}
