import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { api } from "../api/client";
import type { User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useDevMode } from "../hooks/useDevMode";
import { Icon, Mark } from "./Icons";
import { useToast } from "./Toasts";

/** Search on every page; it opens the auctions list filtered by the words typed. */
function HeadSearch({ id, className }: { id: string; className: string }) {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  function submit(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    navigate(q ? `/auctions?q=${encodeURIComponent(q)}` : "/auctions");
  }
  return (
    <form className={`head-search ${className}`} role="search" onSubmit={submit}>
      <label className="vh" htmlFor={id}>
        Search auctions
      </label>
      <Icon name="search" />
      <input
        id={id}
        className="input"
        type="search"
        placeholder="Search items"
        autoComplete="off"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
    </form>
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
    <footer className="site-foot slim">
      <div className="wrap">
        <span>Adal &middot; Senior project, Fall 2026</span>
        <span>
          <Link to="/how-it-works">How bidding works</Link> &middot; Checkout is simulated. No money moves.
          {dev ? (
            <>
              {" "}
              &middot; <Link to="/dev/mailbox">Dev mailbox</Link>
            </>
          ) : null}
        </span>
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
  const { pathname } = useLocation();
  // The landing page and the auctions list already have a search field of their own.
  const showSearch = pathname !== "/" && pathname !== "/auctions";
  const isLanding = pathname === "/";

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
      <Link to="/how-it-works">How it works</Link>
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
    <div className={isLanding ? "site-root landing" : "site-root"}>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="site-head">
        <div className="wrap">
          <Link className="brand" to="/">
            <Mark />
            Adal
          </Link>
          <nav className="site-nav" aria-label="Main">
            {navLinks}
          </nav>
          <div className="acts">
            {showSearch ? <HeadSearch id="hs-d" className="desk-only" /> : null}
            {accountActions}
          </div>
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
        {showSearch ? <HeadSearch id="hs-m" className="phone-only" /> : null}
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
    </div>
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
          <Link className="brand" to="/">
            <Mark />
            Adal
          </Link>
          <p className="quote">
            Every bid weighs the <i>same</i>.
          </p>
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
