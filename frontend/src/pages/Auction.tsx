import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { api, isApiError, noteServerTime, ApiError } from "../api/client";
import type { AuctionDetail, AuctionEvent, AuctionPublic, Bid, Viewer } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icons";
import { Loading } from "../components/Layout";
import { NoPhoto } from "../components/LotCard";
import { SlidingNumber } from "../components/SlidingNumber";
import { EndingSoon, StatusPill } from "../components/StatusPill";
import { useToast } from "../components/Toasts";
import { useAuctionSocket } from "../hooks/useAuctionSocket";
import { categoryName, useCategories } from "../hooks/useCategories";
import { useNow } from "../hooks/useNow";
import { phaseOf } from "../lib/auction";
import { countdown, dateLong, ENDING_SOON_MS, formatName, fromCents, money, parseAmount, timeOfDay, toCents } from "../lib/format";

// ---------------------------------------------------------------------------
// State merging. REST responses, the socket snapshot and events can arrive in any
// order; we always keep the most advanced public state and the latest viewer.

const FINAL = new Set(["closed", "no_sale", "cancelled"]);

function stage(a: AuctionPublic): number {
  if (FINAL.has(a.status)) return 2;
  return a.status === "active" ? 1 : 0;
}

function fresher(a: AuctionPublic, b: AuctionPublic): AuctionPublic {
  if (stage(a) !== stage(b)) return stage(b) > stage(a) ? b : a;
  if (a.bid_count !== b.bid_count) return b.bid_count > a.bid_count ? b : a;
  return Date.parse(b.ends_at) >= Date.parse(a.ends_at) ? b : a;
}

function withViewer(pub: AuctionPublic, viewer: Viewer | null): AuctionDetail {
  if (!viewer) return { ...pub, viewer: null };
  const isLeader = viewer.bidder_number !== null && viewer.bidder_number === pub.leader_bidder_number;
  return { ...pub, viewer: { ...viewer, is_leader: isLeader } };
}

function strip(detail: AuctionDetail): AuctionPublic {
  const { viewer: _viewer, ...pub } = detail;
  return pub;
}

function merge(prev: AuctionDetail | null, incoming: AuctionDetail): AuctionDetail {
  if (!prev) return incoming;
  return withViewer(fresher(strip(prev), strip(incoming)), incoming.viewer ?? prev.viewer);
}

// ---------------------------------------------------------------------------

type Notice =
  | { kind: "rejected"; attempted: string; min: string }
  | { kind: "leading" }
  | { kind: "busy" }
  | { kind: "error"; message: string }
  | null;

function Banner({ children }: { children: ReactNode }) {
  return (
    <div className="banner">
      <Icon name="alert" />
      <span>{children}</span>
    </div>
  );
}

function Info({ children, ok = false }: { children: ReactNode; ok?: boolean }) {
  return (
    <p className={`msg${ok ? " ok" : " info"}`}>
      <Icon name={ok ? "check" : "info"} />
      <span>{children}</span>
    </p>
  );
}

export function AuctionPage() {
  const { id } = useParams();
  const auctionId = Number(id);
  const validId = Number.isInteger(auctionId) && auctionId > 0;
  const { ready, user } = useAuth();
  const toast = useToast();
  const now = useNow();
  const categories = useCategories();

  const [auction, setAuction] = useState<AuctionDetail | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [photo, setPhoto] = useState(0);

  const [presetIndex, setPresetIndex] = useState(0);
  const [custom, setCustom] = useState("");
  const [customError, setCustomError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [submitting, setSubmitting] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const detail = await api<AuctionDetail>(`/api/auctions/${auctionId}`, { signal });
      noteServerTime(detail.server_time, true);
      setLastUpdate(detail.server_time);
      setAuction((prev) => merge(prev, detail));
      setLoadError(null);
    },
    [auctionId],
  );

  // Load once the session is known, and again when the signed-in user changes (viewer differs).
  useEffect(() => {
    if (!ready || !validId) return;
    const ctrl = new AbortController();
    load(ctrl.signal).catch((e) => {
      if (e instanceof DOMException) return;
      if (e instanceof ApiError) setLoadError(e);
    });
    return () => ctrl.abort();
  }, [ready, user?.id, validId, load]);

  const onEvent = useCallback(
    (event: AuctionEvent) => {
      setLastUpdate(new Date().toISOString());
      switch (event.type) {
        case "snapshot":
          noteServerTime(event.auction.server_time, true);
          setAuction((prev) => {
            if (!prev) return withViewer(event.auction, null);
            return withViewer(fresher(strip(prev), event.auction), prev.viewer);
          });
          break;
        case "bid_placed":
          setAuction((prev) => {
            if (!prev || event.bid_count <= prev.bid_count) return prev;
            const bids: Bid[] = [event.bid, ...prev.bids].slice(0, 50);
            return withViewer(
              {
                ...strip(prev),
                status: prev.status === "scheduled" ? "active" : prev.status,
                current_price: event.current_price,
                min_next_bid: event.min_next_bid,
                bid_count: event.bid_count,
                reserve_met: event.reserve_met,
                leader_bidder_number: event.leader_bidder_number,
                ends_at: event.ends_at,
                bids,
              },
              prev.viewer,
            );
          });
          break;
        case "time_extended":
          setAuction((prev) =>
            prev && Date.parse(event.ends_at) > Date.parse(prev.ends_at) ? { ...prev, ends_at: event.ends_at } : prev,
          );
          break;
        case "status_changed":
          setAuction((prev) => {
            if (!prev || FINAL.has(prev.status)) return prev;
            const next = { ...prev, status: event.status };
            if (FINAL.has(event.status)) next.min_next_bid = null;
            return next;
          });
          break;
        case "auction_closed":
          setAuction((prev) =>
            prev
              ? {
                  ...prev,
                  status: event.status,
                  final_price: event.final_price,
                  winner_bidder_number: event.winner_bidder_number,
                  closed_at: event.closed_at,
                  min_next_bid: null,
                }
              : prev,
          );
          // The winner and the seller need their transaction id, which only the REST view carries.
          if (user) load().catch(() => undefined);
          break;
      }
    },
    [load, user],
  );

  const socket = useAuctionSocket(validId ? auctionId : null, onEvent);

  // Tell a leading bidder when someone outbids them.
  const wasLeading = useRef(false);
  const leading = Boolean(auction?.viewer?.is_leader);
  const hasBidderNumber = auction?.viewer?.bidder_number != null;
  useEffect(() => {
    if (
      wasLeading.current &&
      !leading &&
      hasBidderNumber &&
      auction &&
      !FINAL.has(auction.status) &&
      auction.current_price
    ) {
      toast("Outbid", `Someone bid ${money(auction.current_price)}.`);
    }
    wasLeading.current = leading;
  }, [leading, hasBidderNumber, auction, toast]);

  // A new minimum resets the preset choice and clears a stale "leading" notice.
  const minNext = auction?.min_next_bid ?? null;
  useEffect(() => {
    setPresetIndex(0);
    setNotice((n) => (n && n.kind === "leading" ? null : n));
  }, [minNext]);

  useEffect(() => {
    if (auction) document.title = `${auction.title} | Adal`;
  }, [auction]);

  const presets = useMemo(() => {
    if (!auction || !auction.min_next_bid) return [] as string[];
    const base = toCents(auction.min_next_bid);
    const step = Math.max(1, toCents(auction.min_increment));
    return [base, base + step, base + 3 * step].map(fromCents);
  }, [auction]);

  if (!validId || (loadError && loadError.status === 404)) {
    return (
      <div className="pg-auction wrap">
        <div className="empty" style={{ marginTop: 64 }}>
          <p className="title">We could not find this auction.</p>
          <p className="note">It may have been withdrawn, or the link is incomplete.</p>
          <Link className="btn second" to="/auctions">
            Browse auctions
          </Link>
        </div>
      </div>
    );
  }
  if (!auction) {
    return (
      <div className="pg-auction wrap" style={{ paddingTop: 48 }}>
        {loadError ? <Banner>{loadError.message}</Banner> : <Loading label="Loading the auction" />}
      </div>
    );
  }

  const phase = phaseOf(auction, now);
  const remaining = Date.parse(auction.ends_at) - now;
  const ending = phase === "live" && remaining <= ENDING_SOON_MS;
  const viewer = auction.viewer;
  const isSeller = Boolean(viewer?.is_seller);
  const myNumber = viewer?.bidder_number ?? null;
  const isLeader = Boolean(viewer?.is_leader);
  const outbid = phase === "live" && myNumber !== null && !isLeader && auction.bid_count > 0;
  const offline = socket === "lost";
  const myLastBid = myNumber !== null ? auction.bids.find((b) => b.bidder_number === myNumber) ?? null : null;
  const iWon = auction.status === "closed" && myNumber !== null && auction.winner_bidder_number === myNumber;
  const images = auction.images;
  const cover = images[Math.min(photo, images.length - 1)];

  // ----- pill and price label
  let pill: ReactNode;
  if (phase === "ended") {
    if (auction.status === "no_sale") pill = <StatusPill kind="no_sale" />;
    else pill = iWon ? <StatusPill kind="sold" /> : <StatusPill kind="closed" />;
  } else if (phase === "cancelled") pill = <StatusPill kind="cancelled" />;
  else if (phase === "upcoming") pill = <StatusPill kind="upcoming" />;
  else if (phase === "closing") pill = <span className="pill plain"><Icon name="clock" />Closing</span>;
  else if (offline) pill = <StatusPill kind="offline" />;
  else if (isLeader) pill = <StatusPill kind="winning" />;
  else if (outbid) pill = <StatusPill kind="outbid" />;
  else pill = <StatusPill kind="live" />;

  let priceLabel = auction.current_price ? "Current price" : "Starting price";
  let price = auction.current_price ?? auction.starting_price;
  if (phase === "ended" && auction.status === "closed") {
    priceLabel = "Final price";
    price = auction.final_price ?? auction.current_price ?? auction.starting_price;
  } else if (phase === "ended" && auction.status === "no_sale") {
    priceLabel = auction.current_price ? "Last bid" : "Starting price";
  }

  // ----- time line
  let time: ReactNode;
  if (phase === "live" && offline) {
    time = (
      <>
        <b>Last update {lastUpdate ? timeOfDay(lastUpdate) : "unknown"}</b> &middot; Closes {dateLong(auction.ends_at)}
      </>
    );
  } else if (phase === "live") {
    time = (
      <>
        {ending ? (
          <>
            <EndingSoon />{" "}
          </>
        ) : null}
        <b>Ends in {countdown(remaining)}</b> &middot; Closes {dateLong(auction.ends_at)}
      </>
    );
  } else if (phase === "upcoming") {
    time = (
      <>
        <b>Opens in {countdown(Date.parse(auction.starts_at) - now)}</b> &middot; Opens {dateLong(auction.starts_at)}
      </>
    );
  } else if (phase === "closing") {
    time = (
      <>
        <b>Closing</b> &middot; The closing time was {dateLong(auction.ends_at)}
      </>
    );
  } else if (phase === "cancelled") {
    time = <b>Withdrawn by the seller</b>;
  } else {
    time = (
      <>
        <b>Closed</b> {dateLong(auction.closed_at ?? auction.ends_at)}
      </>
    );
  }

  // ----- the chosen amount
  const customAmount = custom.trim() ? parseAmount(custom) : null;
  const amount = custom.trim() ? customAmount : presets[presetIndex] ?? null;
  const signedIn = Boolean(user);
  const verified = Boolean(user?.email_verified);
  const formPaused = offline || isLeader || submitting;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!auction || !auction.min_next_bid) return;
    if (custom.trim()) {
      if (!customAmount) {
        setCustomError("Enter an amount like 260.00.");
        return;
      }
      if (toCents(customAmount) < toCents(auction.min_next_bid)) {
        setCustomError(`The lowest bid you can place now is ${money(auction.min_next_bid)}.`);
        return;
      }
    }
    if (!amount) return;
    setCustomError(null);
    setNotice(null);
    setSubmitting(true);
    try {
      const res = await api<{ bid: Bid; auction: AuctionDetail }>(`/api/auctions/${auction.id}/bids`, {
        body: { amount },
      });
      noteServerTime(res.auction.server_time, true);
      setAuction((prev) => merge(prev, res.auction));
      setCustom("");
      toast("Bid placed", `Your bid of ${money(res.bid.amount)} is now the highest.`);
    } catch (err) {
      if (isApiError(err, "bid_too_low")) {
        setNotice({ kind: "rejected", attempted: amount, min: err.detail("min_next_bid") ?? auction.min_next_bid });
        setCustom("");
        load().catch(() => undefined);
      } else if (isApiError(err, "already_leading")) {
        setNotice({ kind: "leading" });
      } else if (isApiError(err, "busy")) {
        setNotice({ kind: "busy" });
      } else if (
        isApiError(err, "auction_ended") ||
        isApiError(err, "auction_not_started") ||
        isApiError(err, "auction_cancelled")
      ) {
        setNotice({ kind: "error", message: err.message });
        load().catch(() => undefined);
      } else if (err instanceof Error) {
        setNotice({ kind: "error", message: err.message });
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function withdraw() {
    if (!auction) return;
    if (!window.confirm("Withdraw this listing? The auction is cancelled and cannot be reopened.")) return;
    setWithdrawing(true);
    try {
      await api<void>(`/api/listings/${auction.listing_id}`, { method: "DELETE" });
      toast("Listing withdrawn", "The auction is cancelled.");
      await load();
    } catch (err) {
      setNotice({ kind: "error", message: err instanceof Error ? err.message : "The listing could not be withdrawn." });
    } finally {
      setWithdrawing(false);
    }
  }

  // ----- the note under the time line
  let note: ReactNode = null;
  if (phase === "ended" && auction.status === "closed") {
    if (iWon) note = <p className="big-note">You won this auction.</p>;
    else if (isSeller) note = <p className="big-note">Sold for {money(price)}.</p>;
    else note = <p className="big-note">This auction has closed. It sold for {money(price)}.</p>;
  } else if (phase === "ended") {
    note = (
      <p className="big-note">
        {auction.bid_count === 0 ? "There is no winner. Nobody placed a bid." : "There is no winner. The reserve price was not met."}
      </p>
    );
  } else if (phase === "cancelled") {
    note = <p className="big-note">The seller withdrew this listing before any bid.</p>;
  } else if (phase === "upcoming") {
    note = <Info>Bidding opens at the time above. This page updates by itself.</Info>;
  } else if (phase === "closing") {
    note = <Info>The closing time has passed. The result appears here in a moment.</Info>;
  } else if (notice?.kind === "rejected") {
    note = (
      <Banner>
        Your bid of {money(notice.attempted)} was not placed. The price moved to {money(auction.current_price)} before it
        reached the server. Pick {money(auction.min_next_bid ?? notice.min)} or more and try again.
      </Banner>
    );
  } else if (notice?.kind === "busy") {
    note = <Banner>The auction is busy right now and your bid was not placed. Try again.</Banner>;
  } else if (notice?.kind === "error") {
    note = <Banner>{notice.message}</Banner>;
  } else if (notice?.kind === "leading" || isLeader) {
    note = (
      <Info ok>
        {myLastBid && isLeader
          ? `Your bid of ${money(myLastBid.amount)} is the highest. If someone outbids you, this changes here at once.`
          : "You already hold the highest bid."}
      </Info>
    );
  } else if (outbid) {
    note = (
      <Banner>
        Someone bid {money(auction.current_price)}.{myLastBid ? ` Your last bid was ${money(myLastBid.amount)}.` : ""} Choose a
        new amount to bid again.
      </Banner>
    );
  } else if (ending) {
    note = <Info>A bid in the last two minutes extends the closing time by two minutes.</Info>;
  }

  const biddingOpen = phase === "live" && auction.min_next_bid !== null;
  const next = encodeURIComponent(`/auctions/${auction.id}`);

  let actions: ReactNode = null;
  if ((biddingOpen || phase === "upcoming") && isSeller) {
    actions = (
      <>
        <p className="fine">This is your listing. Sellers cannot bid on their own auctions.</p>
        {auction.bid_count === 0 ? (
          <button className="link-btn withdraw" type="button" disabled={withdrawing} onClick={withdraw}>
            {withdrawing ? "Withdrawing" : "Withdraw this listing"}
          </button>
        ) : null}
      </>
    );
  } else if (biddingOpen) {
    const buttonLabel = !signedIn
      ? "Sign in to bid"
      : offline
        ? "Bidding paused"
        : isLeader
          ? "You hold the highest bid"
          : submitting
            ? "Placing bid"
            : amount
              ? `Place bid · ${money(amount)}`
              : "Place bid";
    actions = (
      <form className="bid-form" onSubmit={submit} noValidate>
        {signedIn && !verified ? (
          <Banner>Confirm your email to bid. The link is in your inbox, and you can send it again from the bar above.</Banner>
        ) : null}
        <div className="presets" role="radiogroup" aria-label="Choose your bid">
          {presets.map((p, i) => (
            <label className="preset" key={p}>
              <input
                type="radio"
                name="bid"
                value={p}
                checked={!custom.trim() && presetIndex === i}
                disabled={formPaused}
                onChange={() => {
                  setPresetIndex(i);
                  setCustom("");
                  setCustomError(null);
                }}
              />
              <span>{money(p)}</span>
            </label>
          ))}
        </div>
        <div className={`field${customError ? " bad" : ""}`}>
          <label htmlFor="custom">Other amount</label>
          <input
            className="input"
            id="custom"
            inputMode="decimal"
            autoComplete="off"
            placeholder={`${money(auction.min_next_bid)} or more`}
            value={custom}
            disabled={formPaused}
            aria-describedby="custom-hint"
            aria-invalid={customError ? true : undefined}
            onChange={(e) => {
              setCustom(e.target.value);
              setCustomError(null);
            }}
          />
          {customError ? (
            <p className="msg" id="custom-hint" role="alert">
              <Icon name="alert" />
              <span>{customError}</span>
            </p>
          ) : (
            <span className="hint" id="custom-hint">
              The lowest bid you can place now is {money(auction.min_next_bid)}. Bids go up in steps of at least{" "}
              {money(auction.min_increment)}.
            </span>
          )}
        </div>
        {!signedIn ? (
          <Link className="btn block" to={`/account/sign-in?next=${next}`}>
            {buttonLabel}
          </Link>
        ) : (
          <button className="btn block" type="submit" disabled={formPaused || !verified || !amount}>
            {buttonLabel}
          </button>
        )}
      </form>
    );
  } else if (phase === "ended" && auction.status === "closed" && (iWon || isSeller)) {
    actions = viewer?.transaction_id ? (
      <Link className="btn block" to={`/checkout/${viewer.transaction_id}`}>
        {iWon ? "Continue to checkout" : "View the sale"}
      </Link>
    ) : (
      <p className="fine">Preparing the transaction. The link appears here in a moment.</p>
    );
  } else if (phase === "ended" || phase === "cancelled") {
    actions = (
      <Link className="btn second block" to="/auctions">
        Browse other auctions
      </Link>
    );
  }

  const reserveText =
    auction.reserve_met === null ? "No reserve price" : auction.reserve_met ? "Reserve met" : "Reserve not met";

  return (
    <div className="pg-auction wrap">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/auctions">Auctions</Link> / <span aria-current="page">{auction.title}</span>
      </nav>

      <div className="lot-top">
        <figure className="photo">
          <div className="ph">
            {cover ? <img src={cover.url} alt={`Photo ${photo + 1} of ${auction.title}`} /> : <NoPhoto />}
          </div>
          {images.length > 1 ? (
            <div className="thumbs" role="group" aria-label="Photos">
              {images.map((img, i) => (
                <button
                  key={img.id}
                  type="button"
                  className="thumb"
                  aria-pressed={i === photo}
                  aria-label={`Show photo ${i + 1}`}
                  onClick={() => setPhoto(i)}
                >
                  <img src={img.url} alt="" />
                </button>
              ))}
            </div>
          ) : null}
          <figcaption>Photos are provided by the seller.</figcaption>
        </figure>

        <div className="side">
          <div>
            <h1>{auction.title}</h1>
            <p className="by" style={{ marginTop: 12 }}>
              {categoryName(categories, auction.category)} &middot; {formatName(auction.format)} auction
            </p>
          </div>

          {offline && phase === "live" ? (
            <div className="offline-banner" role="alert">
              <Icon name="alert" />
              <span>Connection lost. Prices on this page may be out of date. Bidding resumes when we reconnect.</span>
            </div>
          ) : null}

          <section className="desk" aria-label="Bidding desk">
            <div className="row">
              {pill}
              <span className="meta">{formatName(auction.format)} auction</span>
            </div>
            <div>
              <p className="label">{priceLabel}</p>
              <p className="figure">
                <SlidingNumber value={money(price)} />
              </p>
            </div>
            <p className="meta">{time}</p>
            <div role="status" aria-live="polite">
              {note}
            </div>
            {actions}
            {biddingOpen ? (
              <>
                <hr className="rule" />
                <p className="fine">
                  A bid is a binding commitment. Bids are checked against the live auction, and the server clock decides
                  the order.
                </p>
              </>
            ) : null}
          </section>
        </div>
      </div>

      <div className="sec">
        <div className="cols">
          <div>
            <h2>About this lot</h2>
            <p className="measure description">{auction.description || "The seller did not add a description."}</p>
          </div>
          <div>
            <h2>Details</h2>
            <dl className="dl">
              <dt>Format</dt>
              <dd>{auction.format === "english" ? "English, ascending bids" : formatName(auction.format)}</dd>
              <dt>{now < Date.parse(auction.starts_at) ? "Opens" : "Opened"}</dt>
              <dd>{dateLong(auction.starts_at)}</dd>
              <dt>{FINAL.has(auction.status) ? "Closed" : "Closes"}</dt>
              <dd>{dateLong(auction.closed_at ?? auction.ends_at)}</dd>
              <dt>Starting price</dt>
              <dd>{money(auction.starting_price)}</dd>
              <dt>Bid step</dt>
              <dd>{money(auction.min_increment)}</dd>
              <dt>Reserve</dt>
              <dd>{reserveText}</dd>
              <dt>Bids</dt>
              <dd>{auction.bid_count}</dd>
            </dl>
          </div>
        </div>
      </div>

      <div className="sec">
        <div className="cols">
          <div>
            <h2>How this auction works</h2>
            <ul className="rules ruled">
              <li>
                <Icon name="check" />
                <span>The highest bid when the clock reaches the closing time wins.</span>
              </li>
              <li>
                <Icon name="check" />
                <span>
                  The first bid must be at least the starting price. Each new bid must be above the current price by at
                  least {money(auction.min_increment)}.
                </span>
              </li>
              <li>
                <Icon name="check" />
                <span>
                  A bid in the last two minutes extends the closing time by two minutes, so nobody wins on a last-second
                  bid they could not answer.
                </span>
              </li>
              <li>
                <Icon name="check" />
                <span>The reserve price is hidden. You are only told whether it is met.</span>
              </li>
            </ul>
          </div>
          <div>
            <h2>Bid history</h2>
            {auction.bids.length === 0 ? (
              <p className="note">No bids yet. The first bid must be at least {money(auction.starting_price)}.</p>
            ) : (
              <table className="tbl">
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Bidder</th>
                    <th scope="col" className="num">
                      Amount
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {auction.bids.map((b, i) => (
                    <tr key={`${b.placed_at}-${b.bidder_number}-${b.amount}`}>
                      <td>{timeOfDay(b.placed_at)}</td>
                      <td>
                        Bidder {b.bidder_number}
                        {myNumber === b.bidder_number ? " (you)" : ""}
                      </td>
                      <td className="num">{i === 0 ? <b>{money(b.amount)}</b> : money(b.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="note" style={{ marginTop: 12 }}>
              Bidders are shown by number, never by name.
              {auction.bid_count > auction.bids.length ? ` The latest ${auction.bids.length} of ${auction.bid_count} bids are shown.` : ""}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
