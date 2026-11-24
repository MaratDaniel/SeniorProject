import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
import { Icon } from "../components/Icons";
import { money } from "../lib/format";

const FAQ = [
  {
    q: "What happens if two people bid at the same moment?",
    a: "Every bid is checked against the live state of the auction when it is processed. The server clock decides the order, and only one bid can be the highest. The other bidder is told straight away that the price moved, and what to do next.",
  },
  {
    q: "Can I see the reserve price?",
    a: "No. A seller may set a reserve, and it stays hidden from bidders. In an English auction you are only told whether it is met.",
  },
  {
    q: "Why does Adal ask for a code when I buy?",
    a: "Finishing a purchase needs a fresh code from your authenticator app, so someone using your signed-in browser cannot buy in your name. Sellers and admins also use a code every time they sign in.",
  },
  {
    q: "When does an auction close?",
    a: "At the closing time written beside each countdown, set by the server clock. In an English auction, a bid in the last two minutes extends the closing time by two minutes.",
  },
  {
    q: "Is any money really charged?",
    a: "Not in this version. Checkout is simulated: no card is charged and no money moves.",
  },
];

function Faq() {
  const [open, setOpen] = useState(0);
  return (
    <div className="acc">
      {FAQ.map((item, i) => {
        const isOpen = open === i;
        return (
          <div key={item.q} className={`acc-item${isOpen ? " open" : ""}`}>
            <h3>
              <button
                className="acc-btn"
                type="button"
                aria-expanded={isOpen}
                aria-controls={`faq-${i}`}
                onClick={() => setOpen(isOpen ? -1 : i)}
              >
                {item.q}
                <svg className="pm icon" aria-hidden="true">
                  <use href="#i-plus" />
                </svg>
              </button>
            </h3>
            <div className="acc-panel" id={`faq-${i}`} role="region">
              <div>
                <p>{item.a}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

const FORMATS = [
  { name: "English", rule: "The price rises with each bid. The highest bid at the close wins.", live: true },
  { name: "Dutch", rule: "The price falls on a schedule. The first buyer to accept the current price wins.", live: false },
  { name: "Sealed first-price", rule: "Everyone submits one hidden bid. The highest bidder wins and pays what they bid.", live: false },
  { name: "Sealed second-price", rule: "Everyone submits one hidden bid. The highest bidder wins and pays the second-highest bid.", live: false },
];

const STEPS = [
  {
    t: "See the rules",
    d: "The format, closing time, bid step and whether the reserve is met are on the page before you bid.",
  },
  {
    t: "Place one bid",
    d: "Pick a preset or type an amount. The button repeats what you are about to commit.",
  },
  {
    t: "The server decides",
    d: "It checks your bid against the live auction. If the price moved, you are told what to do next.",
  },
];

export function HowItWorks() {
  const location = useLocation();

  useEffect(() => {
    document.title = "How it works | Adal";
  }, []);

  useEffect(() => {
    if (!location.hash) return;
    const el = document.getElementById(location.hash.slice(1));
    if (el) el.scrollIntoView({ block: "start" });
  }, [location.hash]);

  return (
    <div className="pg-how">
      <div className="wrap">
        <header className="hw-head">
          <h1>How bidding works</h1>
          <p className="lede">One clock, one winner, one price. Every rule is on the page before you bid.</p>
        </header>

        <section className="hw-steps" id="how" aria-labelledby="h-how">
          <div>
            <h2 className="hw-h" id="h-how">
              Bid in three steps
            </h2>
            <ol>
              {STEPS.map((step) => (
                <li key={step.t}>
                  <b>{step.t}</b>
                  <span>{step.d}</span>
                </li>
              ))}
            </ol>
            <p className="hw-note">
              The closing time is written beside every countdown, and new bids appear for every watcher without
              refreshing the page.
            </p>
          </div>
          <div className="desk" role="group" aria-label="Example bidding desk">
            <div className="row">
              <span className="pill live">
                <Icon name="dot" />
                Live
              </span>
              <span className="meta">Example</span>
            </div>
            <div>
              <p className="label">Current price</p>
              <p className="figure">{money("245.00", "USD")}</p>
            </div>
            <p className="meta">
              <b>Ends in 00:12:40</b> &middot; Closes Thursday 12 November, 18:00
            </p>
            <div className="presets" role="radiogroup" aria-label="Example bid amounts">
              {["250.00", "255.00", "265.00"].map((v, i) => (
                <label className="preset" key={v}>
                  <input type="radio" name="example-bid" defaultChecked={i === 0} />
                  <span>{money(v, "USD")}</span>
                </label>
              ))}
            </div>
            <Link className="btn block" to="/auctions">
              Browse live auctions
            </Link>
            <p className="fine">This desk is an example with made-up amounts.</p>
          </div>
        </section>

        <section className="hw-formats" id="formats" aria-labelledby="h-formats">
          <h2 className="hw-h" id="h-formats">
            Four ways to sell
          </h2>
          <ul>
            {FORMATS.map((f) => (
              <li key={f.name}>
                <h3>{f.name}</h3>
                <p>{f.rule}</p>
                <span className={`tag${f.live ? "" : " soon"}`}>{f.live ? "Available" : "Coming soon"}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="hw-faq" id="faq" aria-labelledby="h-faq">
          <h2 className="hw-h" id="h-faq">
            Questions
          </h2>
          <Faq />
        </section>

        <section className="hw-end" aria-labelledby="h-end">
          <h2 className="hw-h" id="h-end">
            Ready to bid?
          </h2>
          <div className="hw-actions">
            <Link className="btn" to="/auctions">
              Browse auctions
            </Link>
            <Link className="btn second" to="/account/sign-up">
              Create an account
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
