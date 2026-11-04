# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Decided in the requirements document: React frontend, Django + Django REST Framework backend, Django Channels (WebSockets) for live updates, PostgreSQL with row-level locking, Docker for portability. The interface is responsive on desktop and mobile browsers.

## Users
Primary audience at launch: the general public, buying and selling in an open marketplace (confirmed by the team).
- **Buyer:** finds an auction and places a bid without help; needs to trust the price and the clock.
- **Seller:** chooses the right selling mechanism for the goods and configures start, end and reserve.
- **Admin:** reviews flagged listings, transactions and the audit log.

## Product Purpose
Adal is a web auction platform where bidding stays correct and fast even when many people bid at the same moment: one winner and one price, every time. Success means correct results under concurrent load, a first-time buyer who can bid without help, and security that goes beyond a password.

## Positioning
The seller picks the auction format per listing (English, Dutch, sealed first-price, or sealed second-price/Vickrey) on one engine, and the platform is built to explain how it stays correct under simultaneous bids. Most platforms offer one or two formats; eBay offers ascending bids with automatic bidding, and the Royal FloraHolland clock offers a falling price.

## Operating Context
- Bids are validated against the live state of the auction when processed; the server clock is the only authority.
- Every watcher sees new bids, price, remaining time and status without refreshing (95% within 1 second).
- Auctions close automatically; each sale creates exactly one transaction, followed by a simulated checkout.
- Auction statuses: scheduled, active, closed, no_sale, cancelled.
- Accounts: email verification, three roles, TOTP MFA at login (mandatory for sellers and admins), and a fresh MFA code to finalize a purchase.
- Phasing: Fall 2026 MVP covers accounts, listings, English auctions with sniping protection, closing, checkout with step-up MFA and the audit log. Spring 2027 adds Dutch, sealed first-price and Vickrey, notifications, the admin dashboard and full evaluation.

## Capabilities and Constraints
- Out of scope: real payments, identity verification (KYC), advanced fraud and reputation scoring, native mobile apps.
- Stretch goals: tamper-evident bid ledger, reputation checks, large-scale load deployment.
- Security targets: OWASP Top Ten (2021) items A01, A02, A03, A05, A07, A09; audit log entries cannot be edited through the application.
- Reserve price is hidden from bidders; English auctions show only whether it is met.
- Open decisions marked [TBD] in the document: minimum increment (fixed or percentage), sniping values, sealed-bid revision before close, email delivery of notifications.
- Currency is undecided; no symbol is specified in the document.

## Brand Commitments
- Name: **Adal**, meaning fair and honest. The brand uses English only.
- Voice: plain, exact and calm; no exclamation marks, emoji or hype. Not flashy, not gambling-like.

## Evidence on Hand
- Requirements and design document: Online_Auction_Service_Requirements_and_Design_v2.docx, with diagrams and a buyer-page wireframe.
- A brandbook at https://claude.ai/artifact/TbaDcisGpKsF6WTLMWZeA1 (private) and the prior TuraLot_Brand_Book.pdf.
- No real users, testimonials, listings, photography or traffic data exist yet. Do not fabricate them.

## Product Principles
1. Correctness is the product: one winner and one price, every time.
2. Show the rules before the user acts, never after.
3. Make the live state (price, time, status) the clearest thing on screen.
4. Protect the purchase: a stolen session alone must not complete one.
5. Adding an auction format means adding one strategy, not changing the engine.

## Accessibility & Inclusion
Interface works responsively on desktop and mobile browsers; a first-time buyer completes a bid without help. No formal accessibility standard is named in the document.
