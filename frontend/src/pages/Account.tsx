import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router";
import { api, isApiError, safeNext, setSession } from "../api/client";
import type { MfaSetup, Role, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icons";
import { ErrorBanner, FieldError, Loading } from "../components/Layout";
import { useToast } from "../components/Toasts";
import { useDevMode } from "../hooks/useDevMode";
import { timeOfDay } from "../lib/format";

function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} | Adal`;
  }, [title]);
}

function Panel({ id, title, children }: { id: string; title: ReactNode; children: ReactNode }) {
  return (
    <section className="panel enter" aria-labelledby={id}>
      <h1 id={id}>{title}</h1>
      {children}
    </section>
  );
}

function PasswordInput({
  id,
  value,
  onChange,
  autoComplete,
  describedBy,
  invalid,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete: string;
  describedBy?: string;
  invalid?: boolean;
}) {
  const [shown, setShown] = useState(false);
  return (
    <div className="pwd">
      <input
        className="input"
        id={id}
        type={shown ? "text" : "password"}
        autoComplete={autoComplete}
        value={value}
        required
        aria-describedby={describedBy}
        aria-invalid={invalid ? true : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
      <button type="button" className="link-btn" aria-controls={id} onClick={() => setShown((s) => !s)}>
        {shown ? "Hide" : "Show"}
      </button>
    </div>
  );
}

function CodeInput({ id, value, onChange }: { id: string; value: string; onChange: (v: string) => void }) {
  return (
    <input
      className="input codebox"
      id={id}
      inputMode="numeric"
      autoComplete="one-time-code"
      maxLength={6}
      placeholder="000000"
      required
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
    />
  );
}

/** After sign-in: sellers and admins without two-step sign-in go set it up first (it is mandatory for them). */
function destinationAfterSignIn(user: User, next: string): string {
  if (user.role !== "buyer" && !user.mfa_enabled) return `/account/security?next=${encodeURIComponent(next)}`;
  return next;
}

// ---------------------------------------------------------------------------

export function SignIn() {
  usePageTitle("Sign in");
  const { ready, user, login, loginMfa } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));

  const [step, setStep] = useState<"password" | "code" | "recovery">("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [ticket, setTicket] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const finished = useRef(false);

  function done(u: User) {
    finished.current = true;
    toast("Signed in", `Welcome back, ${u.email}.`);
    navigate(destinationAfterSignIn(u, next), { replace: true });
  }

  if (ready && user && !finished.current && step === "password" && !busy) {
    return <Navigate to={next} replace />;
  }

  async function submitPassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await login(email.trim(), password);
      if (result.status === "ok") {
        done(result.user);
        return;
      }
      setTicket(result.mfa_ticket);
      setPassword("");
      setStep("code");
    } catch (err) {
      if (isApiError(err, "invalid_credentials"))
        setError("The email or password does not match. Check them and try again, or reset your password.");
      else if (isApiError(err, "account_locked")) {
        const until = err.detail("locked_until");
        setError(
          until
            ? `This account is locked after too many attempts. Try again after ${timeOfDay(until)}.`
            : "This account is locked after too many attempts. Try again later.",
        );
      } else setError(err instanceof Error ? err.message : "Sign-in failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: FormEvent, value: string) {
    e.preventDefault();
    if (!ticket) return;
    setError(null);
    setBusy(true);
    try {
      done(await loginMfa(ticket, value.trim()));
    } catch (err) {
      if (isApiError(err, "invalid_code"))
        setError(
          step === "recovery"
            ? "That recovery code is not right or was already used."
            : "That code is not right or has expired. Wait for the next code and try again.",
        );
      else if (isApiError(err, "ticket_expired")) {
        setStep("password");
        setTicket(null);
        setError("The sign-in step expired. Enter your password again.");
      } else if (isApiError(err, "account_locked")) {
        setStep("password");
        setTicket(null);
        setError("This account is locked after too many attempts. Try again later.");
      } else setError(err instanceof Error ? err.message : "Sign-in failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (step === "code") {
    return (
      <Panel id="t-co" title={<>Enter your <i>code</i></>}>
        <p className="alt">Open your authenticator app and type the 6-digit code for Adal.</p>
        {error ? <ErrorBanner>{error}</ErrorBanner> : null}
        <form onSubmit={(e) => submitCode(e, code)}>
          <div className="field">
            <label htmlFor="c1">6-digit code</label>
            <CodeInput id="c1" value={code} onChange={setCode} />
          </div>
          <button className="btn block" type="submit" disabled={busy || code.length !== 6}>
            {busy ? "Checking" : "Continue"}
          </button>
        </form>
        <p className="alt">
          Lost your device?{" "}
          <button
            className="link-btn"
            type="button"
            onClick={() => {
              setError(null);
              setStep("recovery");
            }}
          >
            Use a recovery code
          </button>
        </p>
      </Panel>
    );
  }

  if (step === "recovery") {
    return (
      <Panel id="t-rc" title={<>Use a recovery <i>code</i></>}>
        <p className="alt">Each recovery code works once. You saved them when you turned on two-step sign-in.</p>
        {error ? <ErrorBanner>{error}</ErrorBanner> : null}
        <form onSubmit={(e) => submitCode(e, recovery)}>
          <div className="field">
            <label htmlFor="r1">Recovery code</label>
            <input
              className="input"
              id="r1"
              autoComplete="off"
              spellCheck={false}
              required
              placeholder="abcd-efgh"
              value={recovery}
              onChange={(e) => setRecovery(e.target.value)}
            />
          </div>
          <button className="btn block" type="submit" disabled={busy || !recovery.trim()}>
            {busy ? "Checking" : "Continue"}
          </button>
        </form>
        <p className="alt">
          <button
            className="link-btn"
            type="button"
            onClick={() => {
              setError(null);
              setStep("code");
            }}
          >
            Back to the 6-digit code
          </button>
        </p>
      </Panel>
    );
  }

  return (
    <Panel id="t-in" title={<>Sign in to <i>Adal</i></>}>
      {error ? <ErrorBanner>{error}</ErrorBanner> : null}
      <form onSubmit={submitPassword}>
        <div className="field">
          <label htmlFor="e1">Email</label>
          <input
            className="input"
            id="e1"
            type="email"
            autoComplete="email"
            placeholder="name@example.com"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="p1">Password</label>
          <PasswordInput id="p1" value={password} onChange={setPassword} autoComplete="current-password" />
        </div>
        <div className="row2">
          <span />
          <Link to="/account/forgot">Forgot password</Link>
        </div>
        <button className="btn block" type="submit" disabled={busy}>
          {busy ? "Signing in" : "Sign in"}
        </button>
      </form>
      <p className="alt">
        New to Adal? <Link to="/account/sign-up">Create an account</Link>
      </p>
    </Panel>
  );
}

// ---------------------------------------------------------------------------

export function SignUp() {
  usePageTitle("Create your account");
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Extract<Role, "buyer" | "seller">>("buyer");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    if (password.length < 10) {
      setFieldErrors({ password: "Use at least 10 characters." });
      return;
    }
    setBusy(true);
    try {
      await api<{ user: User }>("/api/auth/register", { body: { email: email.trim(), password, role }, auth: false });
      navigate("/account/check-email", { state: { email: email.trim() } });
    } catch (err) {
      if (isApiError(err, "email_taken")) setFieldErrors({ email: "An account with this email already exists. Sign in instead." });
      else if (isApiError(err, "weak_password")) setFieldErrors({ password: err.message });
      else if (isApiError(err, "validation_error")) {
        const fields = err.fieldErrors();
        setFieldErrors(fields);
        if (Object.keys(fields).length === 0) setError(err.message);
      } else setError(err instanceof Error ? err.message : "The account could not be created. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel id="t-cr" title={<>Create your <i>account</i></>}>
      {error ? <ErrorBanner>{error}</ErrorBanner> : null}
      <form onSubmit={submit} noValidate>
        <div className={`field${fieldErrors.email ? " bad" : ""}`}>
          <label htmlFor="e2">Email</label>
          <input
            className="input"
            id="e2"
            type="email"
            autoComplete="email"
            required
            value={email}
            aria-invalid={fieldErrors.email ? true : undefined}
            aria-describedby={fieldErrors.email ? "e2-err" : "e2h"}
            onChange={(e) => setEmail(e.target.value)}
          />
          {fieldErrors.email ? (
            <FieldError id="e2-err">{fieldErrors.email}</FieldError>
          ) : (
            <span className="hint" id="e2h">
              Other bidders only ever see a number, never your email.
            </span>
          )}
        </div>
        <div className={`field${fieldErrors.password ? " bad" : ""}`}>
          <label htmlFor="p2">Password</label>
          <PasswordInput
            id="p2"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            describedBy="p2h"
            invalid={Boolean(fieldErrors.password)}
          />
          {fieldErrors.password ? (
            <FieldError id="p2h">{fieldErrors.password}</FieldError>
          ) : (
            <span className="hint" id="p2h">
              At least 10 characters. A phrase of several words works well.
            </span>
          )}
        </div>
        <div className="field">
          <span className="label">I want to</span>
          <div className="presets two-up" role="radiogroup" aria-label="Role">
            <label className="preset">
              <input type="radio" name="role" checked={role === "buyer"} onChange={() => setRole("buyer")} />
              <span>Buy</span>
            </label>
            <label className="preset">
              <input type="radio" name="role" checked={role === "seller"} onChange={() => setRole("seller")} />
              <span>Buy and sell</span>
            </label>
          </div>
          <span className="hint">Selling needs two-step sign-in, set up after you verify your email.</span>
        </div>
        <button className="btn block" type="submit" disabled={busy}>
          {busy ? "Creating account" : "Create account"}
        </button>
      </form>
      <p className="alt">
        Already have an account? <Link to="/account/sign-in">Sign in</Link>
      </p>
    </Panel>
  );
}

// ---------------------------------------------------------------------------

function ResendForm({ initialEmail = "" }: { initialEmail?: string }) {
  const toast = useToast();
  const [email, setEmail] = useState(initialEmail);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function resend(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api("/api/auth/resend-verification", { body: { email: email.trim() }, auth: false });
      toast("Link sent", "If this address has an account that is not yet confirmed, a new link is on its way.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The link could not be sent. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={resend}>
      {error ? <ErrorBanner>{error}</ErrorBanner> : null}
      <div className="field">
        <label htmlFor="re1">Email</label>
        <input
          className="input"
          id="re1"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <button className="btn second" type="submit" disabled={busy || !email.trim()}>
        {busy ? "Sending" : "Send the link again"}
      </button>
    </form>
  );
}

export function CheckEmail() {
  usePageTitle("Check your email");
  const location = useLocation();
  const dev = useDevMode();
  const state = location.state as { email?: unknown } | null;
  const email = typeof state?.email === "string" ? state.email : "";

  return (
    <Panel id="t-ve" title={<>Check your <i>email</i></>}>
      <div className="mail">
        <Icon name="mail" style={{ width: 24, height: 24, marginTop: 2 }} />
        <p>
          We sent a verification link to {email ? <b>{email}</b> : "your address"}. Open it to confirm the address, then
          sign in.
        </p>
      </div>
      <p className="alt">The link works for one use. Nothing arrived? Check your spam folder, or send it again.</p>
      <ResendForm initialEmail={email} />
      <p className="alt">
        <Link to="/account/sign-in">Go to sign in</Link>
        {dev ? (
          <>
            {" "}
            &middot; <Link to="/dev/mailbox">Open the dev mailbox</Link>
          </>
        ) : null}
      </p>
    </Panel>
  );
}

export function VerifyEmail() {
  usePageTitle("Confirm your email");
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { user, reloadUser } = useAuth();
  const [state, setState] = useState<"working" | "done" | "failed">(token ? "working" : "failed");
  const [message, setMessage] = useState<string>("This link is incomplete.");
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true;
    api("/api/auth/verify-email", { body: { token }, auth: false })
      .then(() => {
        setState("done");
        reloadUser().catch(() => undefined);
      })
      .catch((err) => {
        setState("failed");
        if (isApiError(err, "token_expired")) setMessage("This link has expired.");
        else if (isApiError(err, "invalid_token")) setMessage("This link is not valid or was already used.");
        else setMessage(err instanceof Error ? err.message : "The address could not be confirmed.");
      });
  }, [token, reloadUser]);

  if (state === "working") return <Loading label="Confirming your email" />;

  if (state === "done") {
    return (
      <Panel id="t-vd" title={<>Email <i>confirmed</i></>}>
        <p className="alt">Your address is confirmed. You can bid now{user?.role === "seller" ? ", and sell once two-step sign-in is on" : ""}.</p>
        <div className="acts-row">
          {!user ? (
            <Link className="btn" to="/account/sign-in">
              Sign in
            </Link>
          ) : user.role !== "buyer" && !user.mfa_enabled ? (
            <Link className="btn" to="/account/security?next=%2Fsell">
              Turn on two-step sign-in
            </Link>
          ) : (
            <Link className="btn" to="/auctions">
              Browse auctions
            </Link>
          )}
        </div>
      </Panel>
    );
  }

  return (
    <Panel id="t-vf" title={<>Link <i>not valid</i></>}>
      <ErrorBanner>{message}</ErrorBanner>
      <p className="alt">Ask for a new link. It works for one use.</p>
      <ResendForm initialEmail={user?.email ?? ""} />
    </Panel>
  );
}

// ---------------------------------------------------------------------------

function groupKey(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}

export function Security() {
  usePageTitle("Two-step sign-in");
  const { ready, user, reloadUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"), "");
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);
  const started = useRef(false);

  const needsSetup = Boolean(user && !user.mfa_enabled && !codes);

  useEffect(() => {
    if (!needsSetup || started.current) return;
    started.current = true;
    api<MfaSetup>("/api/auth/mfa/setup", { method: "POST" })
      .then(setSetup)
      .catch((err) => {
        if (isApiError(err, "mfa_already_enabled")) reloadUser().catch(() => undefined);
        else setSetupError(err instanceof Error ? err.message : "Two-step sign-in could not be prepared.");
      });
  }, [needsSetup, reloadUser]);

  if (!ready) return <Loading />;
  if (!user) {
    const here = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/account/sign-in?next=${here}`} replace />;
  }

  const afterwards = next || (user.role === "buyer" ? "/me" : "/sell");

  async function enable(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await api<{ recovery_codes: string[] }>("/api/auth/mfa/enable", { body: { code } });
      setCodes(res.recovery_codes);
      await reloadUser();
      toast("Two-step sign-in is on", "Save your recovery codes before you leave this page.");
    } catch (err) {
      if (isApiError(err, "invalid_code")) setError("That code is not right or has expired. Wait for the next code and try again.");
      else if (isApiError(err, "no_pending_setup")) {
        setError("The setup expired. Scan the new code below.");
        setSetup(null);
        started.current = false;
        setCode("");
        api<MfaSetup>("/api/auth/mfa/setup", { method: "POST" }).then(setSetup).catch(() => undefined);
      } else setError(err instanceof Error ? err.message : "Two-step sign-in could not be turned on.");
    } finally {
      setBusy(false);
    }
  }

  if (codes) {
    const text = codes.join("\n");
    return (
      <Panel id="t-codes" title={<>Save your recovery <i>codes</i></>}>
        <p className="alt">
          Each code works once, if you lose access to your authenticator app. Keep them somewhere safe. They are shown only
          this time.
        </p>
        <ul className="codes" aria-label="Recovery codes">
          {codes.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        <div className="acts-row">
          <button
            className="btn second"
            type="button"
            onClick={() => {
              navigator.clipboard
                .writeText(text)
                .then(() => toast("Copied", "The recovery codes are on your clipboard."))
                .catch(() => toast("Not copied", "Select the codes and copy them by hand."));
            }}
          >
            Copy codes
          </button>
          <button className="btn" type="button" onClick={() => navigate(afterwards)}>
            I saved them
          </button>
        </div>
      </Panel>
    );
  }

  if (user.mfa_enabled) {
    return (
      <Panel id="t-on" title={<>Two-step sign-in is <i>on</i></>}>
        <div className="mail">
          <Icon name="lock" style={{ width: 24, height: 24, marginTop: 2 }} />
          <p>Your account asks for a code from your authenticator app when you sign in and when you finish a purchase.</p>
        </div>
        <p className="alt">Lost your device? Use one of your recovery codes at sign-in.</p>
        <div className="acts-row">
          <Link className="btn" to={afterwards}>
            Continue
          </Link>
        </div>
      </Panel>
    );
  }

  return (
    <Panel
      id="t-se"
      title={
        <>
          Turn on <span style={{ whiteSpace: "nowrap" }}>two-step</span> <i>sign-in</i>
        </>
      }
    >
      <p className="alt">
        {user.role === "buyer"
          ? "It adds a code from your phone to your password, and you need it to finish a purchase."
          : "Sellers and admins must use it. It adds a code from your phone to your password."}
      </p>
      <ol className="steps ruled">
        <li>
          <span>Install an authenticator app, such as one from your phone's app store.</span>
        </li>
        <li>
          <span>Scan this code, or type the key by hand.</span>
        </li>
        <li>
          <span>Enter the 6-digit code the app shows.</span>
        </li>
      </ol>
      {setupError ? <ErrorBanner>{setupError}</ErrorBanner> : null}
      {setup ? (
        <div className="qr">
          <img
            src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(setup.qr_svg)}`}
            alt="QR code to add Adal to your authenticator app"
            width={132}
            height={132}
          />
          <div>
            <p className="label">Key</p>
            <p className="key">{groupKey(setup.secret)}</p>
            <p className="note" style={{ marginTop: 6 }}>
              <a href={setup.otpauth_uri}>Open in an authenticator app on this device</a>
            </p>
          </div>
        </div>
      ) : !setupError ? (
        <Loading label="Preparing your code" />
      ) : null}
      {error ? <ErrorBanner>{error}</ErrorBanner> : null}
      <form onSubmit={enable}>
        <div className="field">
          <label htmlFor="c2">6-digit code</label>
          <CodeInput id="c2" value={code} onChange={setCode} />
        </div>
        <button className="btn block" type="submit" disabled={busy || !setup || code.length !== 6}>
          {busy ? "Checking" : "Turn on two-step sign-in"}
        </button>
      </form>
    </Panel>
  );
}

// ---------------------------------------------------------------------------

export function Forgot() {
  usePageTitle("Reset your password");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api("/api/auth/password/forgot", { body: { email: email.trim() }, auth: false });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The link could not be sent. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <Panel id="t-rs" title={<>Check your <i>email</i></>}>
        <div className="mail">
          <Icon name="mail" style={{ width: 24, height: 24, marginTop: 2 }} />
          <p>If an account exists for {email.trim() ? <b>{email.trim()}</b> : "this address"}, we sent a link to reset the password. It works for one use.</p>
        </div>
        <p className="alt">
          <Link to="/account/sign-in">Back to sign in</Link>
        </p>
      </Panel>
    );
  }

  return (
    <Panel id="t-re" title={<>Reset your <i>password</i></>}>
      {error ? <ErrorBanner>{error}</ErrorBanner> : null}
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="e3">Email</label>
          <input
            className="input"
            id="e3"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <span className="hint">We send a one-use link if an account exists for this address.</span>
        </div>
        <button className="btn block" type="submit" disabled={busy}>
          {busy ? "Sending" : "Send reset link"}
        </button>
      </form>
      <p className="alt">
        <Link to="/account/sign-in">Back to sign in</Link>
      </p>
    </Panel>
  );
}

export function ResetPassword() {
  usePageTitle("Choose a new password");
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ReactNode | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setFieldError(null);
    if (password.length < 10) return setFieldError("Use at least 10 characters.");
    if (password !== confirm) return setFieldError("The two passwords do not match.");
    setBusy(true);
    try {
      await api("/api/auth/password/reset", { body: { token, password }, auth: false });
      setSession(null, null);
      setDone(true);
    } catch (err) {
      if (isApiError(err, "invalid_token") || isApiError(err, "token_expired"))
        setError(
          <>
            This reset link has expired or was already used. <Link to="/account/forgot">Ask for a new one</Link>.
          </>,
        );
      else if (isApiError(err, "weak_password")) setFieldError(err.message);
      else setError(err instanceof Error ? err.message : "The password could not be changed.");
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <Panel id="t-rp" title={<>Link <i>incomplete</i></>}>
        <ErrorBanner>This reset link is missing its token. Open the link from the email again, or ask for a new one.</ErrorBanner>
        <p className="alt">
          <Link to="/account/forgot">Ask for a new link</Link>
        </p>
      </Panel>
    );
  }

  if (done) {
    return (
      <Panel id="t-rp" title={<>Password <i>changed</i></>}>
        <p className="alt">Every session was signed out. Sign in with the new password.</p>
        <div className="acts-row">
          <Link className="btn" to="/account/sign-in">
            Sign in
          </Link>
        </div>
      </Panel>
    );
  }

  return (
    <Panel id="t-rp" title={<>Choose a new <i>password</i></>}>
      {error ? <ErrorBanner>{error}</ErrorBanner> : null}
      <form onSubmit={submit} noValidate>
        <div className={`field${fieldError ? " bad" : ""}`}>
          <label htmlFor="np1">New password</label>
          <PasswordInput id="np1" value={password} onChange={setPassword} autoComplete="new-password" describedBy="np1h" />
          <span className="hint" id="np1h">
            At least 10 characters.
          </span>
        </div>
        <div className={`field${fieldError ? " bad" : ""}`}>
          <label htmlFor="np2">Repeat the new password</label>
          <PasswordInput id="np2" value={confirm} onChange={setConfirm} autoComplete="new-password" />
          {fieldError ? <FieldError>{fieldError}</FieldError> : null}
        </div>
        <button className="btn block" type="submit" disabled={busy}>
          {busy ? "Saving" : "Save the new password"}
        </button>
      </form>
    </Panel>
  );
}
