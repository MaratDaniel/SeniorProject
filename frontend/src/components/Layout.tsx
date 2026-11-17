import { useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { api } from "../api/client";
import type { User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useDevMode } from "../hooks/useDevMode";
import { Icon, Mark } from "./Icons";
import { useToast } from "./Toasts";

const NOTICES = [
  "Checkout is simulated: no real payments",
  "One winner, one price",
  "The server clock decides what arrived in time",
  "Bidders are shown by number, never by name",
];

function Notices() {
  return (
    <div className="ann" role="region" aria-label="Notices">
      <div className="ann-track">
        {[0, 1, 2, 3].map((copy) => (
          <ul key={copy} aria-hidden={copy > 0 ? true : undefined}>
            {NOTICES.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        ))}
      </div>
    </div>
  );
}

function VerifyBand({ user }: { user: User }) {
  const toast = useToast();
  const [sending, setSending] = useState(false);
  async function resend() {
    setSending(true);
    try {
      await api("/api/auth/resend-verification", { body: { email: user.email }, auth: false });
      toast("Link sent", "Check your inbox for a new verification link.");
    } catch (e) {
      toast("Not sent", e instanceof Error ? e.message : "Try again in a moment.");
    } finally {
      setSending(false);
    }
  }
  return (
    <div className="verify-band" role="status">
      <div className="wrap">
        <Icon name="mail" />
        <p>
          Confirm your email to bid or sell. We sent a link to <b>{user.email}</b>.
        </p>
        <button className="link-btn" type="button" onClick={resend} disabled={sending}>
          {sending ? "Sending" : "Send it again"}
        </button>
      </div>
    </div>
  );
}

function SiteFooter() {
  const dev = useDevMode();
  return (
    <footer className="site-foot">
      <div className="wrap">
        <div className="cols">
          <div>
            <Link className="brand" to="/" style={{ padding: 0 }}>
              <Mark style={{ width: 40, height: 32 }} />
              Adal
            </Link>
            <p style={{ marginTop: 16, maxWidth: "32ch" }}>
              Fair and honest. An online auction service where every bid weighs the same.
            </p>
          </div>
          <div>
            <h2>Buy</h2>
            <Link to="/auctions">Browse auctions</Link>
            <Link to="/#how">How bidding works</Link>
          </div>
          <div>
            <h2>Sell</h2>
            <Link to="/sell">Create a listing</Link>
            <Link to="/#formats">Selling formats</Link>
          </div>
          <div>
            <h2>Account</h2>
            <Link to="/account/sign-in">Sign in</Link>
            <Link to="/account/sign-up">Create account</Link>
            <Link to="/account/security">Two-step sign-in</Link>
          </div>
        </div>
        <div className="base">
          <span>Adal &middot; Senior project, Fall 2026</span>
          <span>
            Checkout is simulated. No money moves.
            {dev ? (
              <>
                {" "}
                &middot; <Link to="/dev/mailbox">Dev mailbox</Link>
              </>
            ) : null}
          </span>
        </div>
      </div>
    </footer>
  );
}

/** Phones get a menu button instead of the inline nav; the panel closes on navigation and on Escape. */
function useMobileMenu() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
  }, [location.pathname, location.hash]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    // Back to the inline nav when the window grows past the phone breakpoint.
    const wide = window.matchMedia("(min-width: 861px)");
    const onWide = () => wide.matches && setOpen(false);
    document.addEventListener("keydown", onKey);
    wide.addEventListener("change", onWide);
    document.documentElement.classList.add("menu-open");
    return () => {
      document.removeEventListener("keydown", onKey);
      wide.removeEventListener("change", onWide);
      document.documentElement.classList.remove("menu-open");
    };
  }, [open]);

  return [open, setOpen] as const;
}

export function SiteLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [menuOpen, setMenuOpen] = useMobileMenu();

  async function signOut() {
    setMenuOpen(false);
    await logout();
    toast("Signed out", "You are signed out on this device.");
    navigate("/");
  }

  const navLinks = (
    <>
      <NavLink to="/auctions">Auctions</NavLink>
      <NavLink to="/sell">Sell</NavLink>
      <Link to="/#how">How it works</Link>
    </>
  );

  const accountActions = user ? (
    <>
      <NavLink className="btn second" to="/me">
        My account
      </NavLink>
      <button className="link-btn" type="button" onClick={signOut}>
        Sign out
      </button>
    </>
  ) : (
    <>
      <Link className="btn second" to="/account/sign-in">
        Sign in
      </Link>
      <Link className="btn compact" to="/account/sign-up">
        Create account
      </Link>
    </>
  );

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <Notices />
      <header className="site-head">
        <div className="wrap">
          <Link className="brand" to="/">
            <Mark />
            Adal
          </Link>
          <nav className="site-nav" aria-label="Main">
            {navLinks}
          </nav>
          <div className="acts">{accountActions}</div>
          <button
            className="menu-btn"
            type="button"
            aria-expanded={menuOpen}
            aria-controls="m-menu"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <Icon name={menuOpen ? "close" : "menu"} />
            <span>{menuOpen ? "Close" : "Menu"}</span>
          </button>
        </div>
        <div
          className="m-menu"
          id="m-menu"
          hidden={!menuOpen}
          onClick={(e) => {
            if ((e.target as HTMLElement).closest("a")) setMenuOpen(false);
          }}
        >
          <nav className="m-nav" aria-label="Main">
            {navLinks}
          </nav>
          <div className="m-acts">{accountActions}</div>
        </div>
      </header>
      {menuOpen ? <div className="m-scrim" aria-hidden="true" onClick={() => setMenuOpen(false)} /> : null}
      {user && !user.email_verified ? <VerifyBand user={user} /> : null}
      <main id="main">
        <Outlet />
      </main>
      <SiteFooter />
    </>
  );
}

export function AccountLayout() {
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div className="pg-account split">
        <aside className="side dark" aria-label="Adal">
          <div className="ph">
            <img src="/img/beam.jpg" alt="" />
          </div>
          <Link className="brand" to="/">
            <Mark />
            Adal
          </Link>
          <div>
            <p className="quote">
              Every bid weighs the <i>same</i>.
            </p>
            <p className="cred">Beam balance, public domain.</p>
          </div>
        </aside>
        <div className="main">
          <main id="main" className="form-area">
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <p className="note loading" role="status">
      {label}
    </p>
  );
}

/** Sends signed-out visitors to sign in, then back here. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { ready, user } = useAuth();
  const location = useLocation();
  if (!ready) return <Loading />;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/account/sign-in?next=${next}`} replace />;
  }
  return <>{children}</>;
}

export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div className="banner msg err-banner" role="alert">
      <Icon name="alert" />
      <span>{children}</span>
    </div>
  );
}

export function OkNote({ children }: { children: ReactNode }) {
  return (
    <p className="msg ok">
      <Icon name="check" />
      <span>{children}</span>
    </p>
  );
}

export function FieldError({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <p className="msg" id={id} role="alert">
      <Icon name="alert" />
      <span>{children}</span>
    </p>
  );
}
