# Adal web design (handoff)

High-fidelity, static screens for the frontend team. Plain HTML and one CSS file, no build step. Open any `.html` file in a browser (fonts load from Google Fonts, so exact type needs internet). The rules come from `../DESIGN.md` and `../PRODUCT.md`; this folder is what those rules look like on real screens.

## Screens

| File | Screen | Needed for MVP because |
|---|---|---|
| `index.html` | Landing page | First impression; states the promise, shows lots, explains the bid, the four formats, and security |
| `auctions.html` | Browse and filter | A buyer must find an auction (search, format, status, sort) |
| `auction.html` | Auction page with the bidding desk | The core screen. Eight states, switch them with the dashed "Prototype states" bar |
| `account.html` | Create account, verify email, sign in, 6-digit code, set up two-step, recovery code, reset password | Requirements: email verification, roles, TOTP MFA (mandatory for sellers and admins). Ten states |
| `sell.html` | Create a listing | A seller picks the format, price, reserve and schedule, and sees what bidders will see |
| `checkout.html` | Delivery, fresh code, done | Each sale makes one transaction, simulated checkout, fresh MFA code to finalize |

The dashed "Prototype states" bars exist only to show every state to the team. They are not product UI. Do not build them.

## Files

- `adal.css`: all tokens (`:root`) and shared components (header, footer, buttons, fields, presets, bidding desk, lot card, pills, tables). Class names are plain and can map to React components one to one.
- `adal.js`: small motion helpers (sliding highlight, sliding number, toast, accordion, scroll reveal). No dependencies.
- `img/`: four public-domain museum images (beam balance, brass balance, box of weights, Christie's Auction Room print, 1808). These are stand-ins for real listing photos.
- Each page carries its own small `<style>` block for layout that belongs to that page only.

## Component map

| Component | Class | Notes |
|---|---|---|
| Bidding desk | `.desk` | The one raised object. Holds status pill, price (`.figure`), time, presets, one primary button |
| Bid preset | `.presets > .preset` | Three equal radios. First is preselected. Button text repeats the amount |
| Status | `.pill.live / .win / .out / .plain`, `.ending` | Always a word plus an icon |
| Lot card | `.lot` | Photo, status, format, title, price, time |
| Field | `.field`, `.input`, `.select`, `.textarea`, `.codebox` | 48px, visible label, error is a message with an icon and the next step |
| Message | `.msg`, `.banner` | Brass for problems, moss for confirmations. Never color alone |
| Buttons | `.btn`, `.btn.second` | One primary per view |

## Auction page states (`auction.html`)

Live, Ending soon, Winning, Outbid, Bid not placed (price moved, tells the user the next amount), Connection lost (bidding paused, prices flagged as possibly stale), You won (goes to checkout), No sale (reserve not met).
For the backend: the page is driven by price, status, time left, whether the reserve is met, and the lowest allowed next bid. The desk re-renders when any of these change over the WebSocket.

## Palette (lighter green, v2)

The first pass used a deep green (`#3B5F4F` action, `#243A31` fields). It was too heavy, so the web screens now use a fresher, lighter sage. Contrast was computed for every pair.

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--moss` | `#40705A` | Buttons, links, selected states | 5.25:1 with paper text |
| `--moss-hover` | `#4A7A63` | Button hover | 4.54:1 with paper text |
| `--field` / `--moss-deep` | `#3F6E59` / `#2F5545` | Dark photographic fields (hero, security band, sign-in panel), centre to edge | paper text 5.4 to 7.7:1 |
| `--moss-tint` | `#E6F0EA` | Selected preset, live pill, highlights | moss on it 4.8:1 |
| `--sage` | `#DCEAE1` | The footer, now a light band instead of a dark block | ink 14.9:1 |
| `--brass-on-dark` | `#F0CF84` | The one brass word on dark fields (large text only) | 3.9 to 5.6:1 |
| `--soft` | `#E3ECE6` | Secondary text on dark fields | 4.9 to 7:1 |

Paper, card, rule, ink, body, muted and brass are unchanged. `DESIGN.md`, the deck, the report and the brandbook now use the same green.

## Motion

Patterns are taken from Animate UI (animate-ui.com), a React library, and rebuilt in plain CSS and JS in `adal.js` so these static screens need no React. When the team builds in React, the matching Animate UI components can replace them one to one.

| Pattern | Where | Animate UI equivalent |
|---|---|---|
| Sliding highlight | Header nav, status chips, prototype state bars, bid presets, format cards | Tabs, Radio Group |
| Sliding number | The price on the auction page rolls digit by digit when it changes | Sliding Number |
| Accordion | Questions on the landing page | Accordion |
| Toast | "Bid placed" and "Photo added" | Toast |
| Progress | Photo upload on the sell page | Progress |
| Animated checkbox | "Keep me signed in" | Checkbox |
| Entrance | Hero text rises once, sections appear once on scroll | n/a |

Rules: springs for movement, plain eases for fades, every effect plays once, and `prefers-reduced-motion` turns all of it off. Without JavaScript the screens show their normal static state.

## Rules kept on every screen

- One brass word per headline. Brass marks Outbid, Ending soon and the balance point, nothing else.
- Every number is tabular. Every status is a word plus an icon.
- 10px corners on controls, 16px on surfaces. Only the bidding desk has a shadow.
- Targets are at least 44px. Focus is a 2px moss outline. Reduced motion removes all movement.
- Voice is plain and calm: no exclamation marks, no emoji, no hype.
- Bidders are shown by number, never by name. The reserve price is never shown, only whether it is met.

## What is sample content (replace before launch)

- Every lot, price, time, bid history and seller on the pages. Each page says "Sample" near it.
- Photos in `img/`.
- The QR code and key on the two-step screen.
- Landing claims such as "within a second for most watchers" must be verified by the load tests before they go live. The page does not state a number.

## Open decisions that change these screens

From `PRODUCT.md`: minimum increment (the presets assume "current plus a step"), sniping protection values (rule text avoids numbers), whether a sealed bid can be revised before close, email delivery of notifications, and currency (no symbol is shown anywhere). The three non-English formats are shown as "Coming soon"; their bidding desks (Dutch accept-price desk, sealed bid desk) still need designing for Spring 2027.

## Not designed yet

My bids and watchlist, seller listing management and edit, notification center, admin dashboard and audit log (Spring 2027), loading skeletons, 404 and empty search results, and the account menu once signed in.

## Second pass: Resore-style motion and an unslop audit

- Added on the landing page: words of the headline rise out of a clipped line, a slow strip of the four selling formats and their status (pauses on hover), numbered steps that light up in order, and an "Open lot" label that slides over lot photos on hover.
- Unslop audit applied to the HTML and CSS: one non-overshooting ease-out curve instead of springs, no scale pops, the eyebrow label in sentence case without wide tracking. No copy or data changed.
- All of it is transform and opacity only, runs once, and is removed under `prefers-reduced-motion`.
- Credit: the audit follows unslop by Damir Sokolovsky (@heydamir), CC BY 4.0, github.com/heydamir/unslop.

## Third pass: Resore layout ideas, checked with the impeccable detector

- Split landing hero: headline, one primary action and a dashed fact card on the left, the 1808 print full height on the right.
- Centred wordmark in the header with navigation left and account actions right (desktop). Applied to every page except `account.html`, which has its own panel layout.
- A thin notice bar above the header (all pages except `account.html`). It carries true notices only: sample screens, simulated checkout, one winner and one price, the server clock. It scrolls slowly and pauses on hover.
- Removed the second marquee (selling formats). The detector flags looping tickers because they hide content, and the formats already have their own section.
- Not taken from Resore: the yellow field (brass stays a small accent), monospaced uppercase labels (not in DESIGN.md), the product and review sections (no real data).

## Fourth pass

- Removed the small label above headings on every page (a ban in the impeccable craft floor).
- Landing: a sage band with the three promises in large display type and dashed dividers; the four selling formats each carry a small drawn diagram of how the price behaves (rising steps, falling steps, hidden bids with the winner and the price paid); the header now sticks to the top.
- Auctions: the page head pairs the title with a photograph.
- Browser details themed from the palette: text selection, caret, scrollbar, accent colour, link underline offset.
