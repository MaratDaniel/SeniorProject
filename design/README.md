# TuraLot — front-end prototype (demo)

A navigable online-auction marketplace prototype built with plain HTML, CSS and vanilla JavaScript. No framework, no build step, no backend.

**Everything is illustrative.** Auctions, lots, sellers, ratings and prices are made-up sample data. Accounts, bids, registrations and seller questions are simulated and stored only in your browser (LocalStorage). No payments, no real authentication, no messages to sellers.

## Run it

```
cd turalot
python3 -m http.server
# open http://localhost:8000
```

Opening `index.html` directly from disk also works, because mock data is loaded from `js/data.js` and not fetched.

## Project structure

```
turalot/
├── index.html            Home
├── auctions.html         All auctions (search, status filter, sort)
├── auction.html          One auction and its lots
├── lot.html              One lot: gallery, bidding, tabs
├── search.html           Search results with filters
├── categories.html       All categories
├── category.html         One category (same filters as search)
├── auction-house.html    Seller profile
├── saved.html            Saved items, followed searches, followed houses
├── my-bids.html          Demo bid history
├── account.html          Profile, activity, following, settings
├── how-it-works.html     Steps, explanations, FAQ
├── css/
│   ├── variables.css     Colour palette (CSS custom properties)
│   ├── global.css        Base type, layout wrapper, header, nav, footer
│   ├── components.css    Buttons, cards, forms, modals, tabs, toast, dropdown
│   ├── home.css          Hero, tiles, carousel
│   ├── auction.css       Filter sidebar, pagination, list view
│   ├── lot.css           Gallery, bidding panel, item details
│   └── responsive.css    Breakpoints (loaded last)
├── js/
│   ├── i18n.js           UI label table (English only; Kazakh/Russian slots empty)
│   ├── data.js           Mock data: categories, houses, auctions, lots
│   ├── utils.js          State helpers, formatting, icons, image fallback
│   ├── auth.js           Modal component, login / join / forgot-password
│   ├── search.js         Search, category and categories pages
│   ├── auction.js        Auctions, auction and auction-house pages
│   ├── lot.js            Lot page, bidding, inquiry form
│   ├── saved.js          Saved, my-bids and account pages
│   └── app.js            Header, footer, cards, carousels, home, how-it-works, start-up
└── assets/
    ├── logo/             turalot-icon.svg, turalot-wordmark.svg
    ├── icons/            (empty; icons are inline SVG in utils.js)
    └── images/           (empty; see "Adding real photos")
```

Each page file registers a function in `PAGES`; `app.js` runs the one matching `<body data-page="...">`. Scripts load in the order listed above, and `app.js` is last.

## Pages and URL parameters

| Page | Parameters | Notes |
|---|---|---|
| `auctions.html` | `status=Upcoming\|Live\|Completed` | Search, status filter, sort by date or title |
| `auction.html` | `id=a1`…`a6` | Countdown, register, `.ics` calendar download, lot search/sort, 4/8/12 per page, pagination, list/grid toggle |
| `lot.html` | `id=lot-001`…`lot-024` | Gallery, zoom, tabs, bidding, save, share, ask a question, related items |
| `search.html` | `q`, `st`, `cd`, `hs`, `pmin`, `pmax`, `sort` | Filters are reflected in the URL |
| `category.html` | `c=art\|jewelry\|antiques\|furniture\|collectibles\|electronics\|home\|fashion\|coins\|other` | Same filters as search, category fixed |
| `auction-house.html` | `id=h1`…`h4` | Auctions grouped Current / Upcoming / Previous, plus items |

## Demo behaviour

- **Sign in:** any valid email format and any non-empty password works. Registration needs a name, a valid email, an 8+ character password and a matching confirmation. Only name and email are stored, never the password. Google/Apple sign-in is shown as unavailable.
- **Bidding** (`lot.html`): not signed in opens the login modal. Signed in but not registered for that auction opens a demo registration step. Then pick a quick amount or type one; it must be at least the next minimum and in steps of the bid increment. A confirmation modal states the bid is simulated; confirming records it locally and updates the displayed current bid and My bids.
- **Ask a question** and **forgot password** only save or explain locally; nothing is sent.
- **Dates:** auction dates are generated relative to the moment the page loads, so countdowns always have time left and restart on reload. Statuses (Upcoming / Live / Completed) are computed from those dates.
- **Currency and formatting:** Kazakhstani tenge (`₸`), with thousands separators.

## Data model (`js/data.js`)

- `CATS`: `[id, label]` pairs (10 categories).
- `HOUSES`: `{id, name, loc, desc}` (4 fictional houses, 3 in Kazakhstan, 1 in Türkiye).
- `AUCTIONS`: `{id, title, houseId, description, startDate, endDate, location}` (6).
- `LOTS`: `{id, auctionId, lotNumber, title, description, category, estimateMin, estimateMax, startingBid, currentBid, bidIncrement, bidCount, condition, dimensions, location, endDate}` (24; 12 item types, each used twice). Optional `images: [url, ...]`.

The same data feeds every page, so title, lot number, price and seller are identical wherever an item appears.

## State (LocalStorage keys)

`turalot_demo_session`, `turalot_saved_lots`, `turalot_followed_searches`, `turalot_followed_houses`, `turalot_demo_bids`, `turalot_registered`. Account → Settings → "Clear all demo data" removes everything except the session.

## Accessibility and responsiveness

Semantic landmarks, labelled form fields, visible focus rings, `aria-expanded` on menus, modals that trap focus, close on Escape and return focus, reduced-motion support. Breakpoints: mobile ≤767px, tablet 768–1023px, desktop ≥1024px. On mobile the nav and search collapse behind ☰ and ⌕ buttons.

## Adding real photos

Put files in `assets/images/` and add `images: ["assets/images/lot-001-1.jpg", ...]` to a lot in `data.js`. Cards, gallery and zoom then use them. A missing file falls back to a neutral placeholder. Until then, items show generated placeholder tiles.

## Adding translations

Labels in `js/i18n.js` are looked up with `t("key")`; fill the `kk` and `ru` objects and set `LANG`. Only header, footer and navigation labels use this so far; labels on other pages are still inline in the page scripts and need moving into the table first. No language switch is shown until translations exist.

## Known limitations

- Layout was smoke-tested for errors in a simulated browser (jsdom) but not reviewed visually at all target widths.
- Product images are placeholders.
- Not implemented: search-by-image, back-to-top button, a maximum-bid feature (bids are exact amounts), rating/review pages, real localisation.
- The footer's Terms and Privacy links point to a placeholder page.

## Replacing the mock logic later

All data access goes through the lookups in `utils.js` (`lot()`, `auc()`, `house()`) and the `LS` / `toggle()` state helpers, so a backend can replace those without redesigning the pages.
