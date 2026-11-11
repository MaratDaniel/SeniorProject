import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router";
import { api } from "../api/client";
import type { AuctionCard, Page } from "../api/types";
import { Icon } from "../components/Icons";
import { LotCard } from "../components/LotCard";
import { useNow } from "../hooks/useNow";

function HeroWords() {
  // Words rise out of a clipped line once (adal.css .w); removed under reduced motion.
  const words = ["An", "auction", "where", "every", "bid", "weighs", "the"];
  return (
    <h1 className="display" id="h-hero">
      {words.map((w, i) => (
        <span key={w + i}>
          <span className="w">
            <span style={{ ["--i" as string]: i }}>{w}</span>
          </span>{" "}
        </span>
      ))}
      <i>
        <span className="w">
          <span style={{ ["--i" as string]: words.length }}>same</span>
        </span>
      </i>
      .
    </h1>
  );
}

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

function OpenLots() {
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
    <section className="block" aria-labelledby="h-open">
      <div className="sec-head">
        <h2 className="headline" id="h-open">
          {label === "now" ? (
            <>
              Lots open <i>now</i>
            </>
          ) : (
            <>
              Lots opening <i>soon</i>
            </>
          )}
        </h2>
        <Link className="btn second" to="/auctions">
          All auctions
        </Link>
      </div>
      {lots === null ? (
        <p className="note" role="status">
          Loading lots
        </p>
      ) : lots.length === 0 ? (
        <div className="empty">
          <p className="title">No lots are open right now.</p>
          <p className="note">Sellers can list an item in a few minutes. New auctions appear here as soon as they open.</p>
          <Link className="btn" to="/sell">
            Sell an item
          </Link>
        </div>
      ) : (
        <div className="gallery">
          <LotCard card={lots[0]} now={now} variant="big" />
          {lots.length > 1 ? (
            <div className="side">
              {lots.slice(1).map((lot) => (
                <LotCard key={lot.id} card={lot} now={now} variant="side" />
              ))}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

export function Home() {
  const location = useLocation();

  useEffect(() => {
    if (!location.hash) return;
    const el = document.getElementById(location.hash.slice(1));
    if (el) el.scrollIntoView({ block: "start" });
  }, [location.hash]);

  useEffect(() => {
    document.title = "Adal | An auction where every bid weighs the same";
  }, []);

  return (
    <div className="pg-home">
      <section className="hero-split" aria-labelledby="h-hero">
        <div className="hs-copy rise">
          <HeroWords />
          <p className="lede">
            Adal is an online auction service with four selling formats on one engine. One winner and one price, every
            time, even when many people bid at the same moment.
          </p>
          <div className="acts">
            <Link className="btn" to="/auctions">
              Browse auctions <Icon name="arrow" />
            </Link>
            <Link className="btn second" to="/sell">
              Sell an item
            </Link>
          </div>
          <div className="spec">
            <div>
              <h2>Checked on the server</h2>
              <p>Every bid is validated against the live auction before it counts.</p>
            </div>
            <svg
              viewBox="0 0 112 112"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeDasharray="2 5"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <circle cx="56" cy="56" r="52" />
              <circle cx="56" cy="64" r="38" />
              <circle cx="56" cy="72" r="24" />
              <circle cx="56" cy="80" r="11" />
            </svg>
          </div>
        </div>
        <div className="hs-photo">
          <img
            src="/img/auction-room.jpg"
            alt="Hand-coloured print of Christie's Auction Room, London, 1808: a crowd in a skylit hall facing the auctioneer's rostrum"
          />
          <p className="cred">Print: Christie's Auction Room, 1808. Public domain.</p>
        </div>
      </section>

      <section className="band">
        <div className="wrap">
          <ul className="promises" aria-label="What Adal promises">
            <li>
              <h2 className="title">One winner, one price</h2>
              <p>Every bid is checked against the live auction. Two people cannot win the same lot.</p>
            </li>
            <li>
              <h2 className="title">One clock</h2>
              <p>
                The server decides what arrived in time, not your browser. The closing time is written beside every
                countdown.
              </p>
            </li>
            <li>
              <h2 className="title">Everyone sees it at once</h2>
              <p>New bids, the price and the time left update for every watcher without refreshing the page.</p>
            </li>
          </ul>
        </div>
      </section>

      <div className="wrap">
        <OpenLots />

        <section className="block" id="how" aria-labelledby="h-how">
          <div className="how">
            <div>
              <h2 className="headline" id="h-how">
                The rules come <i>before</i> the bid.
              </h2>
              <ol className="ruled">
                <li>
                  <div>
                    <b>See the rules</b>
                    <span>
                      The format, the closing time, the increment and whether the reserve is met are on the page before
                      you bid.
                    </span>
                  </div>
                </li>
                <li>
                  <div>
                    <b>Place one bid</b>
                    <span>Choose a preset or enter an amount. The button repeats the amount you are about to commit.</span>
                  </div>
                </li>
                <li>
                  <div>
                    <b>The server decides</b>
                    <span>
                      Your bid is validated against the live state of the auction. If the price moved, you are told what
                      to do next.
                    </span>
                  </div>
                </li>
              </ol>
            </div>
            <div className="desk-wrap">
              <div className="desk" role="group" aria-label="Example bidding desk">
                <div className="row">
                  <span className="pill live">
                    <Icon name="dot" />
                    Live
                  </span>
                  <span className="meta">English auction</span>
                </div>
                <div>
                  <p className="label">Current price</p>
                  <p className="figure">245.00</p>
                </div>
                <p className="meta">
                  <b>Ends in 00:12:40</b> &middot; Closes Thursday 12 November, 18:00
                </p>
                <div className="presets" role="radiogroup" aria-label="Example bid amounts">
                  {["250.00", "255.00", "265.00"].map((v, i) => (
                    <label className="preset" key={v}>
                      <input type="radio" name="example-bid" defaultChecked={i === 0} />
                      <span>{v}</span>
                    </label>
                  ))}
                </div>
                <Link className="btn block" to="/auctions">
                  Place bid &middot; 250.00
                </Link>
                <p className="fine">A bid is a binding commitment. This example desk uses illustrative amounts.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="block" id="formats" aria-labelledby="h-formats">
          <h2 className="headline" id="h-formats" style={{ marginBottom: 48 }}>
            Four ways to sell, on <i>one</i> engine.
          </h2>
          <ul className="ruled formats">
            <li>
              <svg className="dg" viewBox="0 0 200 80" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden="true">
                <path d="M4 68H44V52H84V38H124V24H164V12H196" />
                <circle cx="196" cy="12" r="5" fill="currentColor" stroke="none" />
              </svg>
              <div>
                <h3>English</h3>
                <p>The price rises with each bid. The highest bid at the close wins.</p>
              </div>
              <span className="tag">Available</span>
            </li>
            <li>
              <svg className="dg" viewBox="0 0 200 80" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden="true">
                <path d="M4 12H44V26H84V40H124V54" />
                <path d="M124 54H196" strokeDasharray="2 5" strokeWidth="1.5" />
                <circle cx="124" cy="54" r="5" fill="currentColor" stroke="none" />
              </svg>
              <div>
                <h3>Dutch</h3>
                <p>The price falls on a schedule. The first buyer to accept the current price wins.</p>
              </div>
              <span className="tag soon">Coming soon</span>
            </li>
            <li>
              <svg className="dg" viewBox="0 0 200 80" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M4 74H196" strokeWidth="1" opacity=".4" />
                <circle cx="40" cy="56" r="5" />
                <circle cx="80" cy="40" r="5" />
                <circle cx="120" cy="16" r="5" fill="currentColor" />
                <circle cx="160" cy="48" r="5" />
                <path d="M120 16H196" strokeDasharray="2 5" strokeWidth="1.5" />
              </svg>
              <div>
                <h3>Sealed first-price</h3>
                <p>Everyone submits one hidden bid. The highest bidder wins and pays what they bid.</p>
              </div>
              <span className="tag soon">Coming soon</span>
            </li>
            <li>
              <svg className="dg" viewBox="0 0 200 80" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M4 74H196" strokeWidth="1" opacity=".4" />
                <circle cx="40" cy="56" r="5" />
                <circle cx="80" cy="40" r="5" />
                <circle cx="120" cy="16" r="5" fill="currentColor" />
                <circle cx="160" cy="48" r="5" />
                <path d="M120 40H196" strokeDasharray="2 5" strokeWidth="1.5" />
              </svg>
              <div>
                <h3>Sealed second-price</h3>
                <p>Everyone submits one hidden bid. The highest bidder wins and pays the second-highest bid.</p>
              </div>
              <span className="tag soon">Coming soon</span>
            </li>
          </ul>
        </section>

        <section className="block" id="faq" aria-labelledby="h-faq">
          <div className="faqwrap">
            <h2 className="headline" id="h-faq">
              Questions, <i>answered</i> plainly.
            </h2>
            <Faq />
          </div>
        </section>
      </div>

      <section className="secure dark" aria-labelledby="h-secure">
        <div className="wrap">
          <div>
            <h2 className="headline" id="h-secure">
              A stolen session cannot finish a <i>purchase</i>.
            </h2>
            <p className="lede" style={{ marginTop: 24 }}>
              Sellers and admins sign in with a second step. Finishing a purchase asks for a fresh code every time, so a
              signed-in browser alone is not enough.
            </p>
            <div style={{ marginTop: 32, display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Link className="btn" to="/account/sign-up">
                Create an account
              </Link>
              <Link className="btn second" to="/account/sign-in">
                Sign in
              </Link>
            </div>
          </div>
          <ul aria-label="Security measures">
            <li>
              <Icon name="lock" />
              <span>Email verification for every account</span>
            </li>
            <li>
              <Icon name="lock" />
              <span>Authenticator code at sign-in, required for sellers</span>
            </li>
            <li>
              <Icon name="lock" />
              <span>A fresh code to finalize a purchase</span>
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}
