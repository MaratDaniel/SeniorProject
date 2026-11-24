import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import type { AuctionCard, Page } from "../api/types";
import { Icon } from "../components/Icons";
import { LotCard } from "../components/LotCard";
import { useNow } from "../hooks/useNow";

const SHORTCUTS = [
  { label: "Live now", to: "/auctions?show=live" },
  { label: "Ending soon", to: "/auctions?show=ending" },
  { label: "Upcoming", to: "/auctions?show=upcoming" },
];

function LiveNow() {
  const now = useNow();
  const [lots, setLots] = useState<AuctionCard[] | null>(null);
  const [label, setLabel] = useState<"now" | "soon">("now");

  useEffect(() => {
    const ctrl = new AbortController();
    (async () => {
      try {
        const live = await api<Page<AuctionCard>>("/api/auctions?status=live&sort=ending_soon&page_size=3", {
          signal: ctrl.signal,
        });
        if (live.items.length > 0) {
          setLots(live.items);
          return;
        }
        const upcoming = await api<Page<AuctionCard>>("/api/auctions?status=upcoming&sort=ending_soon&page_size=3", {
          signal: ctrl.signal,
        });
        setLabel("soon");
        setLots(upcoming.items);
      } catch (e) {
        if (!(e instanceof DOMException)) setLots([]);
      }
    })();
    return () => ctrl.abort();
  }, []);

  return (
    <section className="live-now" aria-labelledby="h-live">
      <div className="sec-head">
        <h2 className="title" id="h-live">
          {label === "now" ? "Live now, ending soonest" : "Opening soon"}
        </h2>
        <Link className="more" to="/auctions">
          All auctions <Icon name="arrow" />
        </Link>
      </div>
      {lots === null ? (
        <p className="note" role="status">
          Loading lots
        </p>
      ) : lots.length === 0 ? (
        <div className="empty">
          <p className="title">No lots are open right now.</p>
          <p className="note">New auctions appear here as soon as they open.</p>
          <Link className="btn" to="/sell">
            Sell an item
          </Link>
        </div>
      ) : (
        <div className="live-list">
          {lots.map((lot) => (
            <LotCard key={lot.id} card={lot} now={now} variant="side" />
          ))}
        </div>
      )}
    </section>
  );
}

export function Home() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");

  useEffect(() => {
    document.title = "Adal | An auction where every bid weighs the same";
  }, []);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const term = q.trim();
    navigate(term ? `/auctions?q=${encodeURIComponent(term)}` : "/auctions");
  }

  return (
    <div className="pg-home pg-landing">
      <section className="land" aria-labelledby="h-hero">
        <div className="land-copy rise">
          <h1 className="display" id="h-hero">
            Bid on what you <i>love</i>.
          </h1>
          <p className="lede">Every bid weighs the same. One winner, one price, and the server clock decides.</p>
          <form className="land-search" role="search" onSubmit={onSearch}>
            <label className="vh" htmlFor="home-q">
              Search auctions
            </label>
            <input
              id="home-q"
              type="search"
              placeholder="Search items, for example lamp or watch"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              autoComplete="off"
            />
            <button className="btn" type="submit">
              Search
            </button>
          </form>
          <ul className="land-chips" aria-label="Browse">
            {SHORTCUTS.map((c) => (
              <li key={c.label}>
                <Link to={c.to}>{c.label}</Link>
              </li>
            ))}
            <li>
              <Link to="/sell">Sell an item</Link>
            </li>
          </ul>
        </div>
        <LiveNow />
      </section>
    </div>
  );
}
