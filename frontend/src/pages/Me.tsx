import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api } from "../api/client";
import type { AuctionCard, Transaction } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icons";
import { ErrorBanner, Loading, RequireAuth } from "../components/Layout";
import { LotCard } from "../components/LotCard";
import { useToast } from "../components/Toasts";
import { useNow } from "../hooks/useNow";
import { dateShort, money } from "../lib/format";

const ROLE_NAMES = { buyer: "Buyer", seller: "Buyer and seller", admin: "Admin" } as const;
const TX_STATUS = { pending: "Waiting for checkout", completed: "Completed", expired: "Expired" } as const;

function useList<T>(path: string | null): { items: T[] | null; error: string | null } {
  const [items, setItems] = useState<T[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!path) return;
    const ctrl = new AbortController();
    api<T[]>(path, { signal: ctrl.signal })
      .then(setItems)
      .catch((e) => {
        if (e instanceof DOMException) return;
        setError(e instanceof Error ? e.message : "This list could not be loaded.");
      });
    return () => ctrl.abort();
  }, [path]);
  return { items, error };
}

export function Me() {
  return (
    <RequireAuth>
      <MePage />
    </RequireAuth>
  );
}

function MePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const now = useNow();
  const isSeller = user?.role === "seller" || user?.role === "admin";
  const bids = useList<AuctionCard>("/api/me/bids");
  const listings = useList<AuctionCard>(isSeller ? "/api/me/listings" : null);
  const txs = useList<Transaction>("/api/transactions");

  useEffect(() => {
    document.title = "My account | Adal";
  }, []);

  if (!user) return <Loading />;

  async function resend() {
    try {
      await api("/api/auth/resend-verification", { body: { email: user!.email }, auth: false });
      toast("Link sent", "Check your inbox for a new verification link.");
    } catch (e) {
      toast("Not sent", e instanceof Error ? e.message : "Try again in a moment.");
    }
  }

  return (
    <div className="pg-me wrap">
      <header className="page-head">
        <h1 className="headline">
          My <i>account</i>
        </h1>
      </header>

      <section className="me-sec" aria-labelledby="h-acc">
        <h2 id="h-acc">Account</h2>
        <dl className="dl">
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Account type</dt>
          <dd>{ROLE_NAMES[user.role]}</dd>
          <dt>Email status</dt>
          <dd>
            {user.email_verified ? (
              <span className="pill win"><Icon name="check" />Confirmed</span>
            ) : (
              <>
                <span className="pill out"><Icon name="alert" />Not confirmed</span>{" "}
                <button className="link-btn" type="button" onClick={resend}>
                  Send the link again
                </button>
              </>
            )}
          </dd>
          <dt>Two-step sign-in</dt>
          <dd>
            {user.mfa_enabled ? (
              <span className="pill win"><Icon name="lock" />On</span>
            ) : (
              <>
                <span className="pill plain">Off</span> <Link to="/account/security">Turn it on</Link>
              </>
            )}
          </dd>
          <dt>Member since</dt>
          <dd>{dateShort(user.created_at)}</dd>
        </dl>
        <div className="acts-row" style={{ marginTop: 24 }}>
          <button
            className="btn second"
            type="button"
            onClick={async () => {
              await logout();
              navigate("/");
            }}
          >
            Sign out
          </button>
        </div>
      </section>

      <section className="me-sec" aria-labelledby="h-tx">
        <h2 id="h-tx">Purchases and sales</h2>
        {txs.error ? <ErrorBanner>{txs.error}</ErrorBanner> : null}
        {txs.items === null && !txs.error ? <Loading /> : null}
        {txs.items && txs.items.length === 0 ? <p className="note">Nothing yet. Auctions you win or sell appear here.</p> : null}
        {txs.items && txs.items.length > 0 ? (
          <table className="tbl">
            <thead>
              <tr>
                <th scope="col">Reference</th>
                <th scope="col">Item</th>
                <th scope="col">Side</th>
                <th scope="col">Status</th>
                <th scope="col" className="num">
                  Amount
                </th>
                <th scope="col">
                  <span className="vh">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {txs.items.map((t) => (
                <tr key={t.id}>
                  <td>{t.reference}</td>
                  <td>
                    <Link to={`/auctions/${t.auction_id}`}>{t.title}</Link>
                  </td>
                  <td>{t.role === "buyer" ? "Bought" : "Sold"}</td>
                  <td>{TX_STATUS[t.status]}</td>
                  <td className="num">{money(t.amount)}</td>
                  <td>
                    <Link to={`/checkout/${t.id}`}>
                      {t.role === "buyer" && t.status === "pending" ? "Complete purchase" : "View"}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>

      <section className="me-sec" aria-labelledby="h-bids">
        <h2 id="h-bids">Auctions I bid on</h2>
        {bids.error ? <ErrorBanner>{bids.error}</ErrorBanner> : null}
        {bids.items === null && !bids.error ? <Loading /> : null}
        {bids.items && bids.items.length === 0 ? (
          <p className="note">
            No bids yet. <Link to="/auctions">Browse auctions</Link>
          </p>
        ) : null}
        {bids.items && bids.items.length > 0 ? (
          <ul className="grid">
            {bids.items.map((c) => (
              <li key={c.id}>
                <LotCard card={c} now={now} />
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      {isSeller ? (
        <section className="me-sec" aria-labelledby="h-listings">
          <div className="sec-head">
            <h2 id="h-listings">My listings</h2>
            <Link className="btn second" to="/sell">
              Create a listing
            </Link>
          </div>
          {listings.error ? <ErrorBanner>{listings.error}</ErrorBanner> : null}
          {listings.items === null && !listings.error ? <Loading /> : null}
          {listings.items && listings.items.length === 0 ? <p className="note">You have not listed anything yet.</p> : null}
          {listings.items && listings.items.length > 0 ? (
            <ul className="grid">
              {listings.items.map((c) => (
                <li key={c.id}>
                  <LotCard card={c} now={now} />
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
