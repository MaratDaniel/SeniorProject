# Adal API contract (MVP, fall 2026)

The front end and back end both build against this file. If something here is wrong or missing, change this file first.

## Conventions

- REST under `/api`, WebSocket under `/ws`, uploaded photos under `/media`. In development the Vite server proxies all three to the backend at `http://127.0.0.1:8000`, so the browser sees one origin.
- JSON everywhere except the photo upload (multipart).
- **Money** is a string with two decimals: `"245.00"`. Never a float. No currency symbol is shown (the currency is undecided).
- **Times** are ISO 8601 in UTC: `"2026-11-12T18:00:00Z"`. The server clock is the only authority; the client shows countdowns using `server_time` to correct its own clock.
- **Auth**: `Authorization: Bearer <access_token>` (JWT, 15 minutes). The refresh token is an httpOnly cookie `adal_refresh` (path `/api/auth`, SameSite=Strict). Keep the access token in memory only. On page load call `POST /api/auth/refresh`; on a `401` with code `token_expired`, refresh once and retry.
- **Errors** always have this shape, with a stable `code` the UI can switch on:

```json
{"error": {"code": "bid_too_low", "message": "Your bid must be at least 250.00.", "details": {"min_next_bid": "250.00"}}}
```

Validation errors are `422` with `code: "validation_error"` and `details.fields` mapping a field name to a message.

## Shared objects

```ts
type Role = "buyer" | "seller" | "admin";

type User = {
  id: number;
  email: string;
  role: Role;
  email_verified: boolean;
  mfa_enabled: boolean;
  created_at: string;
};

type AuctionStatus = "scheduled" | "active" | "closed" | "no_sale" | "cancelled";
type AuctionFormat = "english" | "dutch" | "sealed_first_price" | "vickrey"; // only "english" is accepted in the MVP

type AuctionCard = {
  id: number;
  listing_id: number;
  title: string;
  category: string;            // category slug
  cover_url: string | null;    // "/media/…" or null
  format: AuctionFormat;
  status: AuctionStatus;
  starting_price: string;
  current_price: string | null; // null until the first bid
  bid_count: number;
  starts_at: string;
  ends_at: string;              // moves later when sniping protection extends it
  reserve_met: boolean | null;  // null when the listing has no reserve; the reserve amount is never sent to bidders
};

type Bid = { bidder_number: number; amount: string; placed_at: string }; // bidders are shown by number, never by name

type AuctionDetail = AuctionCard & {
  description: string;
  images: { id: number; url: string }[];  // first is the cover
  min_increment: string;
  min_next_bid: string | null;  // the smallest amount the next bid may have; null when bidding is closed
  server_time: string;
  bids: Bid[];                  // newest first, at most 50
  leader_bidder_number: number | null;
  winner_bidder_number: number | null;
  final_price: string | null;
  closed_at: string | null;
  viewer: null | {              // null for anonymous requests
    is_seller: boolean;
    bidder_number: number | null; // set once the viewer has bid on this auction
    is_leader: boolean;
    transaction_id: number | null; // set for the winner and the seller after a sale
  };
};

type Listing = {
  id: number;
  title: string;
  description: string;
  category: string;
  starting_price: string;
  reserve_price: string | null; // only returned to the owner
  images: { id: number; url: string }[];
  status: "active" | "withdrawn";
  auction_id: number | null;
  created_at: string;
};

type Delivery = { full_name: string; address: string; city: string; postal_code: string };

type Transaction = {
  id: number;
  reference: string;            // "TX-000042"
  auction_id: number;
  title: string;
  cover_url: string | null;
  amount: string;
  status: "pending" | "completed" | "expired";
  role: "buyer" | "seller";     // the viewer's side of the sale
  created_at: string;
  expires_at: string;           // a pending sale expires 48 hours after the close
  completed_at: string | null;
  won_at: string;               // when the auction closed
  delivery: Delivery | null;    // filled in at checkout; visible to the buyer and the seller only
};
```

## Accounts and security

| Method and path | Auth | Body | Success | Error codes |
|---|---|---|---|---|
| `POST /api/auth/register` | none | `{email, password, role: "buyer"\|"seller"}` | `201 {user}`; sends a verification email | `email_taken` 409, `weak_password` 422, `rate_limited` 429 |
| `POST /api/auth/verify-email` | none | `{token}` | `200 {verified: true}` | `invalid_token` 400, `token_expired` 400 |
| `POST /api/auth/resend-verification` | none | `{email}` | `202 {}` (always, no account enumeration) | `rate_limited` 429 |
| `POST /api/auth/login` | none | `{email, password}` | `200 {status: "ok", access_token, user}` and the refresh cookie, **or** `200 {status: "mfa_required", mfa_ticket}` | `invalid_credentials` 401, `account_locked` 423 (`details.locked_until`), `rate_limited` 429 |
| `POST /api/auth/login/mfa` | none | `{mfa_ticket, code}` (`code` is a 6-digit TOTP code or a recovery code like `abcd-efgh`) | `200 {status: "ok", access_token, user}` and the refresh cookie | `invalid_code` 401, `ticket_expired` 401, `account_locked` 423, `rate_limited` 429 |
| `POST /api/auth/refresh` | cookie | none | `200 {access_token, user}` and a rotated cookie | `no_session` 401 |
| `POST /api/auth/logout` | cookie | none | `204` | none |
| `GET /api/auth/me` | bearer | none | `200 User` | `not_authenticated` 401, `token_expired` 401 |
| `POST /api/auth/mfa/setup` | bearer | none | `200 {secret, otpauth_uri, qr_svg}` (`qr_svg` is an `<svg>` string) | `mfa_already_enabled` 409 |
| `POST /api/auth/mfa/enable` | bearer | `{code}` | `200 {recovery_codes: string[]}` (10 codes, shown once) | `invalid_code` 400, `no_pending_setup` 409 |
| `POST /api/auth/password/forgot` | none | `{email}` | `202 {}` (always) | `rate_limited` 429 |
| `POST /api/auth/password/reset` | none | `{token, password}` | `204`; signs out every session | `invalid_token` 400, `token_expired` 400, `weak_password` 422 |

Rules: passwords are 10 to 128 characters. Logging in works before the email is verified, but bidding and selling return `403 email_not_verified` until it is. Two-step sign-in (TOTP) is mandatory for sellers and admins: their selling endpoints return `403 mfa_setup_required` until it is enabled. A buyer needs it to finish a purchase. Five failed logins lock the account for 15 minutes.

## Listings and auctions

| Method and path | Auth | Body or query | Success | Error codes |
|---|---|---|---|---|
| `GET /api/categories` | none | | `200 [{slug, name}]` | |
| `POST /api/uploads/images` | seller | multipart, field `file`; JPEG or PNG, at most 5 MB | `201 {id, url}` | `unsupported_image` 400, `image_too_large` 413 |
| `POST /api/listings` | seller | `{title (3–80), description (≤4000), category, starting_price, reserve_price?, image_ids: number[] (≤8, first is the cover)}` | `201 Listing` | `validation_error` 422, `email_not_verified` 403, `mfa_setup_required` 403 |
| `GET /api/listings/{id}` | optional | | `200 Listing` | `not_found` 404 |
| `PATCH /api/listings/{id}` | owner | any subset of the create fields | `200 Listing` | `listing_locked` 409 (price fields after the first bid), `forbidden` 403 |
| `DELETE /api/listings/{id}` | owner | | `204` (withdraws the listing and cancels its auction) | `has_bids` 409, `forbidden` 403 |
| `POST /api/listings/{id}/auction` | owner | `{format: "english", starts_at, ends_at, min_increment}` | `201 AuctionDetail` | `auction_exists` 409, `format_unavailable` 400 (Dutch and sealed formats are spring 2027), `invalid_schedule` 400 |
| `GET /api/auctions` | none | `q`, `category`, `format`, `status=live\|upcoming\|ended\|all` (default `all`, which hides cancelled), `sort=ending_soon\|newest\|price_low\|price_high` (default `ending_soon`), `page` (from 1), `page_size` (≤48, default 24) | `200 {items: AuctionCard[], total, page, page_size}` | |
| `GET /api/auctions/{id}` | optional | | `200 AuctionDetail` | `not_found` 404 |
| `POST /api/auctions/{id}/bids` | bearer | `{amount}` | `201 {bid: Bid, auction: AuctionDetail}` | `auction_not_started` 409, `auction_ended` 409, `auction_cancelled` 409, `bid_too_low` 409 (`details.min_next_bid`), `already_leading` 409 (the viewer already holds the highest bid; also stops a double click from raising the price against yourself), `seller_cannot_bid` 409, `email_not_verified` 403, `rate_limited` 429, `busy` 503 (lock wait timed out under load; retry), `not_found` 404 |
| `GET /api/me/listings` | seller | | `200 AuctionCard[]` (own auctions, including cancelled) | |
| `GET /api/me/bids` | bearer | | `200 AuctionCard[]` (auctions the viewer has bid on) | |

Schedule rules: `ends_at` is after `starts_at`, the auction lasts at least 5 minutes and at most 30 days, and `starts_at` is not in the past (a minute of slack is allowed; send the current time to open now). `min_increment` is a fixed amount set by the seller, at least `0.01`.

English rules: the first bid must be at least `starting_price`; every later bid must be at least `current_price + min_increment`. A seller cannot bid on their own auction. A bid placed in the last 2 minutes extends `ends_at` by 2 minutes. At the close, the highest bid wins if it meets the reserve; otherwise the auction ends as `no_sale`.

## Checkout

| Method and path | Auth | Body | Success | Error codes |
|---|---|---|---|---|
| `GET /api/transactions` | bearer | | `200 Transaction[]` (as buyer or seller) | |
| `GET /api/transactions/{id}` | buyer or seller | | `200 Transaction` | `not_found` 404 |
| `POST /api/transactions/{id}/confirm` | buyer | `{code, delivery: Delivery}` | `200 Transaction` (now `completed`) | `invalid_code` 400 (wrong, stale or already used), `mfa_required` 403 (set up two-step first), `transaction_not_pending` 409, `transaction_expired` 410, `rate_limited` 429 |

The code must be a fresh TOTP code. Recovery codes are not accepted here, and a code can be used only once. Payment is simulated: no card data is collected or stored.

## Live updates

`WS /ws/auctions/{id}` needs no auth (English auctions are public). The client sends nothing. On every (re)connect the server first sends a `snapshot`, so a reconnecting client simply replaces its state.

```ts
type AuctionEvent =
  | { type: "snapshot"; auction: Omit<AuctionDetail, "viewer"> }
  | { type: "status_changed"; auction_id: number; status: AuctionStatus }
  | { type: "bid_placed"; auction_id: number; bid: Bid; current_price: string; min_next_bid: string;
      bid_count: number; reserve_met: boolean | null; leader_bidder_number: number; ends_at: string }
  | { type: "time_extended"; auction_id: number; ends_at: string }
  | { type: "auction_closed"; auction_id: number; status: "closed" | "no_sale";
      final_price: string | null; winner_bidder_number: number | null; closed_at: string };
```

Events are sent only after the database commit. `status_changed` can also carry `"cancelled"` (the seller withdrew the listing before any bid). Because the server subscribes before it reads the snapshot, an event may repeat something the snapshot already contains: ignore a `bid_placed` whose `bid_count` is not greater than the one you hold. If the socket drops, the auction page shows "Connection lost", pauses the bid button and reconnects with backoff; a REST `GET /api/auctions/{id}` is a valid fallback.

## Development helpers

- `GET /api/dev/outbox` (only when `ADAL_ENV=dev`): `200 [{id, to, subject, body, links: string[], created_at}]`, newest first. Email is not delivered in development; verification and reset links land here.
- `GET /api/admin/audit?limit=100` (admin with two-step): `200 [{id, at, actor_id, action, target_type, target_id, data}]`. The audit log is append-only; the database rejects updates and deletes.
