import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { api } from "../api/client";
import type { AuctionCard, Category, Page } from "../api/types";
import { Icon } from "../components/Icons";
import { LotCard } from "../components/LotCard";
import { useNow } from "../hooks/useNow";

const PAGE_SIZE = 24;

type Chip = { key: string; label: string; status: string; sort?: string };
const CHIPS: Chip[] = [
  { key: "all", label: "All", status: "all" },
  { key: "live", label: "Live", status: "live" },
  { key: "ending", label: "Ending soon", status: "live", sort: "ending_soon" },
  { key: "upcoming", label: "Upcoming", status: "upcoming" },
  { key: "ended", label: "Closed", status: "ended" },
];

const FORMATS = [
  { value: "", label: "All formats" },
  { value: "english", label: "English" },
  { value: "dutch", label: "Dutch" },
  { value: "sealed_first_price", label: "Sealed first-price" },
  { value: "vickrey", label: "Sealed second-price" },
];

const SORTS = [
  { value: "ending_soon", label: "Ending soonest" },
  { value: "newest", label: "Newest" },
  { value: "price_low", label: "Price, low to high" },
  { value: "price_high", label: "Price, high to low" },
];

export function Auctions() {
  const now = useNow();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const format = params.get("format") ?? "";
  const category = params.get("category") ?? "";
  const chipKey = params.get("show") ?? "all";
  const sort = params.get("sort") ?? "ending_soon";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);

  const chip = CHIPS.find((c) => c.key === chipKey) ?? CHIPS[0];

  const [search, setSearch] = useState(q);
  const [categories, setCategories] = useState<Category[]>([]);
  const [result, setResult] = useState<Page<AuctionCard> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Auctions | Adal";
    api<Category[]>("/api/categories")
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  // Keep the text box in step with the URL (back/forward), and debounce typing into the URL.
  useEffect(() => setSearch(q), [q]);
  useEffect(() => {
    if (search === q) return;
    const t = window.setTimeout(() => update({ q: search || null, page: null }), 300);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const query = useMemo(() => {
    const s = new URLSearchParams();
    if (q) s.set("q", q);
    if (format) s.set("format", format);
    if (category) s.set("category", category);
    s.set("status", chip.status);
    s.set("sort", chip.sort ?? sort);
    s.set("page", String(page));
    s.set("page_size", String(PAGE_SIZE));
    return s.toString();
  }, [q, format, category, chip, sort, page]);

  useEffect(() => {
    const ctrl = new AbortController();
    setError(null);
    api<Page<AuctionCard>>(`/api/auctions?${query}`, { signal: ctrl.signal })
      .then(setResult)
      .catch((e) => {
        if (e instanceof DOMException) return;
        setError(e instanceof Error ? e.message : "The auctions could not be loaded.");
      });
    return () => ctrl.abort();
  }, [query]);

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    setParams(next, { replace: false });
  }

  const total = result?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const filtered = Boolean(q || format || category || chipKey !== "all");

  return (
    <div className="pg-auctions wrap">
      <header className="page-head split">
        <h1 className="headline">
          Every lot, with its rules <i>shown</i> first
        </h1>
        <div className="ph-band">
          <img src="/img/balance.jpg" alt="" />
        </div>
      </header>

      <form className="filters" role="search" aria-label="Filter auctions" onSubmit={(e) => e.preventDefault()}>
        <div className="field search-f">
          <label htmlFor="q">Search</label>
          <div className="search">
            <Icon name="search" />
            <input
              className="input"
              id="q"
              type="search"
              placeholder="Search by item name"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
        <div className="field">
          <label htmlFor="fmt">Selling format</label>
          <select className="select" id="fmt" value={format} onChange={(e) => update({ format: e.target.value, page: null })}>
            {FORMATS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="sort">Sort by</label>
          <select
            className="select"
            id="sort"
            value={chip.sort ?? sort}
            disabled={Boolean(chip.sort)}
            onChange={(e) => update({ sort: e.target.value, page: null })}
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="cat">Category</label>
          <select className="select" id="cat" value={category} onChange={(e) => update({ category: e.target.value, page: null })}>
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </form>

      <div className="chips" role="group" aria-label="Auction status">
        {CHIPS.map((c) => (
          <button
            key={c.key}
            className="chip"
            type="button"
            aria-pressed={c.key === chip.key}
            onClick={() => update({ show: c.key === "all" ? null : c.key, page: null })}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="count">
        <p className="label" aria-live="polite">
          {result === null ? "Loading auctions" : total === 1 ? "1 auction" : `${total} auctions`}
        </p>
        {filtered ? (
          <button
            className="link-btn"
            type="button"
            onClick={() => {
              setSearch("");
              setParams(new URLSearchParams());
            }}
          >
            Clear filters
          </button>
        ) : null}
      </div>

      {error ? (
        <div className="banner msg err-banner" role="alert">
          <Icon name="alert" />
          <span>{error}</span>
        </div>
      ) : null}

      {result && result.items.length === 0 ? (
        <div className="empty">
          <p className="title">No auctions match these filters.</p>
          <p className="note">Try another word, another format, or show every status.</p>
        </div>
      ) : (
        <ul className="grid">
          {(result?.items ?? []).map((card) => (
            <li key={card.id}>
              <LotCard card={card} now={now} />
            </li>
          ))}
        </ul>
      )}

      {pages > 1 ? (
        <nav className="pager" aria-label="Pages">
          <button className="btn second" type="button" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
            Previous
          </button>
          <span className="label pager-at">
            Page {page} of {pages}
          </span>
          <button className="btn second" type="button" disabled={page >= pages} onClick={() => update({ page: String(page + 1) })}>
            Next
          </button>
        </nav>
      ) : null}
    </div>
  );
}
