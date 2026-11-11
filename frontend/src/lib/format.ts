import type { AuctionFormat } from "../api/types";

// Money stays a decimal string end to end. Arithmetic is done in integer cents.

const AMOUNT_RE = /^\d+(\.\d{1,2})?$/;

export function toCents(amount: string): number {
  const [whole, frac = ""] = amount.split(".");
  return Number(whole) * 100 + Number((frac + "00").slice(0, 2));
}

export function fromCents(cents: number): string {
  const whole = Math.floor(cents / 100);
  const frac = String(cents % 100).padStart(2, "0");
  return `${whole}.${frac}`;
}

/** "1180.00" -> "1,180.00". Never shows a currency symbol (the currency is undecided). */
export function money(amount: string | null | undefined): string {
  if (amount === null || amount === undefined) return "";
  const [whole, frac = "00"] = amount.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${grouped}.${(frac + "00").slice(0, 2)}`;
}

/** Parses what a person types ("1,250", "1250.5") into "1250.50", or null. */
export function parseAmount(input: string): string | null {
  const cleaned = input.trim().replace(/[,\s]/g, "");
  if (!AMOUNT_RE.test(cleaned)) return null;
  return fromCents(toCents(cleaned));
}

const dayFmt = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long" });
const dayYearFmt = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
const hmFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const hmsFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const shortFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

/** "Thursday 12 November, 18:00" in the viewer's time zone (the year is added when it is not this year). */
export function dateLong(iso: string): string {
  const d = new Date(iso);
  const day = d.getFullYear() === new Date().getFullYear() ? dayFmt.format(d) : dayYearFmt.format(d);
  return `${day}, ${hmFmt.format(d)}`;
}

export function timeOfDay(iso: string): string {
  return hmsFmt.format(new Date(iso));
}

export function dateShort(iso: string): string {
  return shortFmt.format(new Date(iso));
}

/** Remaining time as "00:12:40", or "2 days 04:10:00" when longer than a day. */
export function countdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const days = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const clock = [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
  if (days === 0) return clock;
  return `${days} ${days === 1 ? "day" : "days"} ${clock}`;
}

export const FORMAT_NAMES: Record<AuctionFormat, string> = {
  english: "English",
  dutch: "Dutch",
  sealed_first_price: "Sealed first-price",
  vickrey: "Sealed second-price",
};

export function formatName(format: AuctionFormat): string {
  return FORMAT_NAMES[format] ?? format;
}

/** Value for <input type="datetime-local"> in local time. */
export function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Reads a datetime-local value (local time) and returns a UTC ISO string, or null. */
export function fromLocalInput(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export const ENDING_SOON_MS = 2 * 60 * 1000;
