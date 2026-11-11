import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { api, ApiError, isApiError } from "../api/client";
import type { Delivery, Transaction } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Icon } from "../components/Icons";
import { ErrorBanner, FieldError, Loading, RequireAuth } from "../components/Layout";
import { NoPhoto } from "../components/LotCard";
import { useToast } from "../components/Toasts";
import { dateLong, money } from "../lib/format";

type Step = "delivery" | "confirm" | "done";

const LIMITS: Record<keyof Delivery, number> = { full_name: 120, address: 200, city: 80, postal_code: 20 };
const LABELS: Record<keyof Delivery, string> = {
  full_name: "Full name",
  address: "Address",
  city: "City",
  postal_code: "Postal code",
};

function Flow({ step }: { step: Step }) {
  const order: Step[] = ["delivery", "confirm", "done"];
  const at = order.indexOf(step);
  const names = ["Delivery", "Confirm with a code", "Done"];
  return (
    <ol className="flow" aria-label="Checkout steps">
      {order.map((s, i) => (
        <li key={s} className={i < at ? "done" : undefined} aria-current={i === at ? "step" : undefined}>
          <span className="n">{i + 1}</span>
          {names[i]}
        </li>
      ))}
    </ol>
  );
}

function Summary({ tx }: { tx: Transaction }) {
  return (
    <aside className="sum" aria-label="Order summary">
      <div className="lotrow">
        {tx.cover_url ? <img src={tx.cover_url} alt="" /> : <div className="mini-ph"><NoPhoto /></div>}
        <div>
          <b>{tx.title}</b>
          <span className="note">
            {tx.role === "buyer" ? "You won" : "Sold"} on {dateLong(tx.won_at)}
          </span>
        </div>
      </div>
      <dl>
        <dt>Winning bid</dt>
        <dd>{money(tx.amount)}</dd>
        <dt>Fees</dt>
        <dd>None in this version</dd>
        <dt className="t">Total</dt>
        <dd className="t">{money(tx.amount)}</dd>
      </dl>
      <p className="note">
        Reference {tx.reference}. <Link to={`/auctions/${tx.auction_id}`}>View the auction</Link>
      </p>
    </aside>
  );
}

export function Checkout() {
  return (
    <RequireAuth>
      <CheckoutPage />
    </RequireAuth>
  );
}

function CheckoutPage() {
  const { id } = useParams();
  const txId = Number(id);
  const { user } = useAuth();
  const toast = useToast();
  const [tx, setTx] = useState<Transaction | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [step, setStep] = useState<Step>("delivery");
  const [delivery, setDelivery] = useState<Delivery>({ full_name: "", address: "", city: "", postal_code: "" });
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof Delivery, string>>>({});
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    document.title = "Checkout | Adal";
    if (!Number.isInteger(txId) || txId <= 0) return;
    const ctrl = new AbortController();
    api<Transaction>(`/api/transactions/${txId}`, { signal: ctrl.signal })
      .then((t) => {
        setTx(t);
        if (t.status === "completed") setStep("done");
      })
      .catch((e) => {
        if (e instanceof ApiError) setLoadError(e);
      });
    return () => ctrl.abort();
  }, [txId]);

  if (!Number.isInteger(txId) || txId <= 0 || loadError?.status === 404) {
    return (
      <div className="pg-checkout wrap">
        <div className="empty" style={{ marginTop: 64 }}>
          <p className="title">We could not find this purchase.</p>
          <p className="note">Open it from the auction page or from My account.</p>
          <Link className="btn second" to="/me">
            My account
          </Link>
        </div>
      </div>
    );
  }
  if (!tx) {
    return (
      <div className="pg-checkout wrap" style={{ paddingTop: 48 }}>
        {loadError ? <ErrorBanner>{loadError.message}</ErrorBanner> : <Loading label="Loading your purchase" />}
      </div>
    );
  }

  function validateDelivery(): boolean {
    const errs: Partial<Record<keyof Delivery, string>> = {};
    (Object.keys(LIMITS) as (keyof Delivery)[]).forEach((key) => {
      const value = delivery[key].trim();
      if (!value) errs[key] = `Enter your ${LABELS[key].toLowerCase()}.`;
      else if (value.length > LIMITS[key]) errs[key] = `Keep this to ${LIMITS[key]} characters.`;
    });
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function confirm(e: FormEvent) {
    e.preventDefault();
    if (!tx) return;
    setCodeError(null);
    setError(null);
    setBusy(true);
    try {
      const trimmed: Delivery = {
        full_name: delivery.full_name.trim(),
        address: delivery.address.trim(),
        city: delivery.city.trim(),
        postal_code: delivery.postal_code.trim(),
      };
      const done = await api<Transaction>(`/api/transactions/${tx.id}/confirm`, { body: { code, delivery: trimmed } });
      setTx(done);
      setStep("done");
      toast("Purchase complete", `Reference ${done.reference}. Nothing was charged.`);
    } catch (err) {
      setCode("");
      if (isApiError(err, "invalid_code"))
        setCodeError("That code is not right or has expired. Your purchase is not complete. Wait for the next code and try again.");
      else if (isApiError(err, "transaction_expired")) setTx({ ...tx, status: "expired" });
      else if (isApiError(err, "transaction_not_pending")) {
        api<Transaction>(`/api/transactions/${tx.id}`)
          .then((t) => {
            setTx(t);
            if (t.status === "completed") setStep("done");
          })
          .catch(() => undefined);
      } else if (isApiError(err, "validation_error")) {
        const fields = err.fieldErrors();
        const mapped: Partial<Record<keyof Delivery, string>> = {};
        for (const [k, v] of Object.entries(fields)) {
          const key = k.replace(/^delivery\./, "") as keyof Delivery;
          if (key in LIMITS) mapped[key] = v;
        }
        if (Object.keys(mapped).length) {
          setFieldErrors(mapped);
          setStep("delivery");
        } else setError(err.message);
      } else setError(err instanceof Error ? err.message : "The purchase could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  // ----- seller's view: a read-only summary of the sale
  if (tx.role === "seller") {
    return (
      <div className="pg-checkout wrap">
        <header className="page-head">
          <h1 className="headline">
            Your <i>sale</i>
          </h1>
        </header>
        <div className="lay">
          <div className="step">
            <h2>
              {tx.status === "completed"
                ? "The buyer completed the purchase"
                : tx.status === "expired"
                  ? "The purchase expired"
                  : "Waiting for the buyer"}
            </h2>
            {tx.status === "completed" && tx.delivery ? (
              <dl className="dl">
                <dt>Name</dt>
                <dd>{tx.delivery.full_name}</dd>
                <dt>Address</dt>
                <dd>{tx.delivery.address}</dd>
                <dt>City</dt>
                <dd>{tx.delivery.city}</dd>
                <dt>Postal code</dt>
                <dd>{tx.delivery.postal_code}</dd>
              </dl>
            ) : tx.status === "pending" ? (
              <p className="measure">
                The winner has until {dateLong(tx.expires_at)} to confirm the purchase with a fresh code. You will see the
                delivery details here once they do.
              </p>
            ) : (
              <p className="measure">The winner did not complete the purchase in time. No money moved.</p>
            )}
            <p className="note">Payment is simulated. No card is charged and no money moves in this version.</p>
          </div>
          <Summary tx={tx} />
        </div>
      </div>
    );
  }

  if (tx.status === "expired") {
    return (
      <div className="pg-checkout wrap">
        <header className="page-head">
          <h1 className="headline">
            This purchase <i>expired</i>
          </h1>
        </header>
        <div className="lay">
          <div className="step">
            <p className="measure">
              The purchase had to be confirmed by {dateLong(tx.expires_at)}. It was not completed and nothing was charged.
            </p>
            <Link className="btn second" to="/auctions" style={{ alignSelf: "flex-start" }}>
              Back to auctions
            </Link>
          </div>
          <Summary tx={tx} />
        </div>
      </div>
    );
  }

  return (
    <div className="pg-checkout wrap">
      <header className="page-head">
        <h1 className="headline">
          {step === "done" ? (
            <>
              Thank <i>you</i>
            </>
          ) : (
            <>
              Complete your <i>purchase</i>
            </>
          )}
        </h1>
      </header>
      <Flow step={step} />
      <div className="lay">
        <div>
          {error ? <ErrorBanner>{error}</ErrorBanner> : null}

          {step === "delivery" ? (
            <section className="step enter" aria-labelledby="t1">
              <h2 id="t1">Delivery and payment</h2>
              <p className="note">Confirm by {dateLong(tx.expires_at)}, or the purchase expires.</p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (validateDelivery()) setStep("confirm");
                }}
                noValidate
              >
                {(["full_name", "address"] as const).map((key) => (
                  <div className={`field${fieldErrors[key] ? " bad" : ""}`} key={key}>
                    <label htmlFor={key}>{LABELS[key]}</label>
                    <input
                      className="input"
                      id={key}
                      autoComplete={key === "full_name" ? "name" : "street-address"}
                      maxLength={LIMITS[key]}
                      required
                      value={delivery[key]}
                      onChange={(e) => setDelivery({ ...delivery, [key]: e.target.value })}
                    />
                    {fieldErrors[key] ? <FieldError>{fieldErrors[key]}</FieldError> : null}
                  </div>
                ))}
                <div className="two">
                  {(["city", "postal_code"] as const).map((key) => (
                    <div className={`field${fieldErrors[key] ? " bad" : ""}`} key={key}>
                      <label htmlFor={key}>{LABELS[key]}</label>
                      <input
                        className="input"
                        id={key}
                        autoComplete={key === "city" ? "address-level2" : "postal-code"}
                        maxLength={LIMITS[key]}
                        required
                        value={delivery[key]}
                        onChange={(e) => setDelivery({ ...delivery, [key]: e.target.value })}
                      />
                      {fieldErrors[key] ? <FieldError>{fieldErrors[key]}</FieldError> : null}
                    </div>
                  ))}
                </div>
                <div className="sim">
                  <Icon name="info" />
                  <p>
                    <b>Simulated payment.</b> No card is charged and no money moves in this version. Completing checkout
                    records the sale.
                  </p>
                </div>
                <button className="btn" type="submit" style={{ alignSelf: "flex-start" }}>
                  Continue
                </button>
              </form>
            </section>
          ) : null}

          {step === "confirm" ? (
            <section className="step enter" aria-labelledby="t2">
              <h2 id="t2">Confirm with a fresh code</h2>
              {user && !user.mfa_enabled ? (
                <>
                  <p className="measure">
                    Finishing a purchase needs a fresh code from an authenticator app, and this account does not have
                    two-step sign-in yet. Set it up, then come back to this page.
                  </p>
                  <Link
                    className="btn"
                    style={{ alignSelf: "flex-start" }}
                    to={`/account/security?next=${encodeURIComponent(`/checkout/${tx.id}`)}`}
                  >
                    Set up two-step sign-in
                  </Link>
                </>
              ) : (
                <>
                  <p className="measure">
                    To protect this purchase, enter the current 6-digit code from your authenticator app. Being signed in is
                    not enough on its own.
                  </p>
                  {codeError ? <ErrorBanner>{codeError}</ErrorBanner> : null}
                  <form onSubmit={confirm} style={{ maxWidth: 420 }}>
                    <div className="field">
                      <label htmlFor="cc">6-digit code</label>
                      <input
                        className="input codebox"
                        id="cc"
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        maxLength={6}
                        placeholder="000000"
                        required
                        value={code}
                        onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                      />
                    </div>
                    <button className="btn" type="submit" disabled={busy || code.length !== 6}>
                      {busy ? "Confirming" : `Confirm purchase · ${money(tx.amount)}`}
                    </button>
                    <button className="link-btn" type="button" style={{ alignSelf: "flex-start" }} onClick={() => setStep("delivery")}>
                      Back to delivery
                    </button>
                  </form>
                </>
              )}
            </section>
          ) : null}

          {step === "done" ? (
            <section className="step enter" aria-labelledby="t3">
              <div className="done-box">
                <span className="tick">
                  <Icon name="check" />
                </span>
                <h2 id="t3">Purchase complete</h2>
                <p className="measure">
                  One transaction was recorded for this auction.
                  {user ? ` A confirmation was sent to ${user.email}.` : ""} The seller will arrange delivery with you.
                </p>
                <p className="note">Reference {tx.reference}. Nothing was charged.</p>
                <Link className="btn second" to="/auctions">
                  Back to auctions
                </Link>
              </div>
            </section>
          ) : null}
        </div>
        <Summary tx={tx} />
      </div>
    </div>
  );
}
