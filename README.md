# Adal: online auction service (senior project, fall 2026)

An online auction service where bidding stays correct when many people bid at once: one winner and one price, every time.

| File | What it is |
|---|---|
| `Adal-presentation.html` | Final deck, one self-contained file (19 slides, ~6 min). Open in a browser; arrows / space / click to move. |
| `Adal-final-report.docx` | Final report, fall 2026. |
| `Adal-report.html` | Earlier draft of the report with the video plan, one self-contained file. |
| `design/` | Web screens for the frontend team: landing, browse, auction page with bidding states, sign-in and two-step, create listing, checkout. Open `design/index.html`. See `design/README.md`. |
| `brandbook/` | Brandbook sources (design canvas). |
| `DESIGN.md` | Design tokens and rules. |
| `PRODUCT.md` | Product context. |
| `Online_Auction_Service_Requirements_and_Design_v2.docx` | Requirements and design (source of truth). |
| `backend/`, `frontend/` | The working system: FastAPI back end and React front end. How to run it is below. |
| `docs/SYSTEM_DESIGN.md` | How the system works, with the full database schema. |
| `docs/API.md` | The API contract between the front end and the back end. |
| `docs/DEMO.md` | How to show the three demos on the running system. |
| `docker-compose.yml` | The whole stack with one command. |

Fonts load from Google Fonts, so the deck needs internet for exact typography.

## Stack

| Part | Choice |
|---|---|
| Front end | React 19, TypeScript, Vite, React Router |
| API | FastAPI (Python 3.13), Pydantic |
| Live updates | WebSockets in FastAPI, fan-out through Redis pub/sub across processes (in memory when Redis is not configured) |
| Database | PostgreSQL with SQLAlchemy 2 and Alembic; row-level locking for bids |
| Accounts | Argon2id passwords, short-lived JWT access tokens, rotating refresh token in an httpOnly cookie, TOTP (pyotp) at sign-in and again at checkout |
| Packaging | Docker Compose: PostgreSQL, Redis, migrations, API, scheduler worker, nginx |

> The design document v2 proposed Django + DRF + Channels. The backend here is FastAPI; the database design, locking, strategy pattern and WebSocket events are the same. The final report records the change.

## Layout

```
backend/
  app/
    engine/        auction engine: base.py (strategy interface), english.py, service.py (locking, close)
    realtime/      WebSocket endpoint and the event broker
    routers/       auth, listings, auctions, transactions, admin, dev
    security/      passwords, tokens, TOTP, rate limiting
    models.py      schema; migrations/ holds the four Alembic migrations
    scheduler.py   opens, closes and expires on time (also runs as app/worker.py)
  tests/           55 tests, including the concurrency and database-constraint tests
  tools/devdb.sh   local PostgreSQL without Docker
  tools/loadtest.py  load measurement for NFR-3 and NFR-4
frontend/          React app built from the screens in design/
docs/API.md        the contract between front end and back end
.github/workflows/ CI: tests, front-end build, Docker smoke test, dependency scan
```

## Run it locally (no Docker)

Back end (needs [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python --require-hashes -r requirements.txt -r requirements-dev.txt
uv venv --python 3.12 tools/.venv
uv pip install --python tools/.venv/bin/python --require-hashes -r tools/devdb-requirements.txt
tools/devdb.sh start                  # PostgreSQL on 127.0.0.1:54329
.venv/bin/python -m app.cli init-env  # writes backend/.env with fresh secrets
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli seed-demo # optional: demo accounts in .demo-accounts.txt, 8 auctions
tools/run-api.sh                      # http://127.0.0.1:8000, API explorer at /api/docs
```

Front end (Node 22.22 or later):

```bash
cd frontend
npm ci
npm run dev                           # http://localhost:5173
```

By default, verification and reset links appear at http://localhost:5173/dev/mailbox. The demo accounts already have two-step sign-in. Add each TOTP secret from `.demo-accounts.txt` to an authenticator app.

To show an auction closing without waiting for its end, run `.venv/bin/python -m app.cli close-in 3 --seconds 30` in `backend/`: live auction 3 then ends in 30 seconds. It works only with `ADAL_ENV=dev`. Open pages pick up the new end on reload.

## Run it with Docker

```bash
cp .env.example .env    # then fill in the three secrets
docker compose up --build
```

Open http://localhost:8080. To add demo data and print the demo accounts: `docker compose run --rm api python -m app.cli seed-demo --accounts-file -`.

## Test account email with Resend

1. Set `ADAL_RESEND_API_KEY` and `ADAL_MAIL_TEST_RECIPIENT` in your local `.env`. Use a sending-only key and the email address you use to sign in to Resend. The default sender is `Adal <onboarding@resend.dev>`, and the worker only picks up messages addressed to your test recipient.
2. Run `docker compose --profile email up --build`. Register with that email address and open the link from your inbox. Use **Forgot password** with the same account to test the reset link. The frontend address in `ADAL_FRONTEND_URL` must be reachable from the device that opens the email.

The backend renders verification and reset emails from its own templates. A new Resend workspace only needs the sending key and the permitted test recipient. Verification links last 24 hours and reset links last one hour.

### Deliver email to other users from a local instance

1. Add a subdomain you control in Resend and publish the DNS records it provides. The sending subdomain does not need a website. See [Resend's domain setup guide](https://resend.com/docs/add-a-domain).
2. Once Resend verifies it, set `ADAL_MAIL_FROM` to an address at that subdomain and clear `ADAL_MAIL_TEST_RECIPIENT` in `.env`. Run `docker compose --profile email up --build` to apply the settings. Adal hides the development mailbox while sending to unrestricted recipients.
3. Set `ADAL_FRONTEND_URL` to the address recipients use to open Adal. `http://localhost:8080` works on the computer running the stack. For a private test on another device on the same network, use the host's reachable LAN address and have testers open that address in the browser. For a public deployment, use `ADAL_ENV=prod`, an HTTPS frontend URL, secure cookies, and a production database.

The worker delivers signup verification, verification resends, password resets, auction wins and sale outcomes, and buyer and seller checkout confirmations. Account emails include local HTML and plain text. Auction and checkout notifications use plain text. Previously queued development-only notifications stay in the outbox and are not sent retroactively.

## Tests

```bash
cd backend
tools/devdb.sh start
.venv/bin/pytest
```

The suite builds a fresh database with the real migration. `tests/test_concurrency.py` is the evidence for NFR-1:

- 25 identical bids at once: exactly one is accepted.
- 25 rising bids at once: every accepted bid is stored, in order, and the final price is the highest accepted bid.
- The close running 10 times at once creates exactly one transaction.
- Bids racing the close: none is stored after the close.

`tests/test_schema_integrity.py` checks that the database itself refuses a broken row. It writes nine invalid rows with plain SQL, for example a winner on an open auction or a bid under another bidder's number, and PostgreSQL rejects each one.

## Load measurement

```bash
cd backend
tools/devdb.sh start
.venv/bin/python -m tools.loadtest                                              # one busy auction
.venv/bin/python -m tools.loadtest --auctions 20 --bidders 5 --pause 1 --bids-each 15   # the target load
```

The tool starts its own API process on the test database, opens the watchers' WebSockets and lets the bidders compete. It fails unless every watcher received every accepted bid. First results, from one API process on a laptop (Apple M5 Pro), 27 November 2026:

| Load | Bid time, p95 (target 300 ms) | Delivery time, p95 (target 1 s) | Lost events |
|---|---|---|---|
| 1 auction, 200 watchers, 25 bidders with no pause | 67 ms | 10 ms | 0 of 6,200 |
| 20 auctions, 4,000 watchers, 100 bidders, about one bid a second each | 47 ms | 15 ms | 0 of 270,000 |
| 20 auctions, 4,000 watchers, 500 bidders, a bid about every 3 s each | 1.7 s | 35 ms | 0 of 469,600 |

Both targets hold at the target load up to about 80 bids a second. Near 100 bids a second one API process saturates and bids start to queue; `docs/SYSTEM_DESIGN.md` has the details.

## CI

GitHub Actions runs on every push to `main` and on every pull request:

- `.github/workflows/ci.yml` runs the backend tests against PostgreSQL 17 and the front-end type-check and build. It also smoke-tests the Docker stack: build, start, seed the demo data, then load the site, the API and a photo through nginx.
- `.github/workflows/dependency-scan.yml` checks every lockfile against the [OSV](https://osv.dev) vulnerability database. It also runs every Monday, because new advisories appear without any change here.

Actions are pinned by commit SHA and the scanner binary by its SHA-256. To run the same scan locally with [osv-scanner](https://github.com/google/osv-scanner):

```bash
osv-scanner scan source --no-resolve -L backend/requirements.txt -L backend/requirements-dev.txt \
  -L backend/tools/devdb-requirements.txt -L frontend/package-lock.json
```

## How correctness is kept

- **One lock per auction.** A bid locks the auction row (`SELECT … FOR UPDATE`), re-reads it, checks it with the database clock and commits. Other bids on the same auction wait; other auctions are not blocked.
- **The server clock decides.** `clock_timestamp()` from PostgreSQL is read after the lock is held. A bid counts only if it is strictly before the end (FR-20).
- **The close takes the same lock.** It is idempotent and re-checks the state, so a bid and the close cannot interleave. Running it twice is safe (UC-7).
- **The database enforces the invariants.** There is one auction per listing, one transaction per auction (unique keys) and one bidder number per bidder. CHECK constraints keep an auction from being half-closed: a winner and a final price exist exactly when it is closed, and the end only moves later. Money is `numeric(12,2)`, never a float.
- **Events go out after the commit.** Watchers never see a bid that was rolled back.
- **Strategy pattern.** Each format is one class (`engine/english.py`). Adding Dutch or sealed formats means registering a strategy in `engine/registry.py`; locking stays in `engine/service.py`.

## Security (OWASP Top Ten 2021)

| Item | What the code does |
|---|---|
| A01 Broken access control | Role and ownership checks on the server for every write; others' sales return 404. |
| A02 Cryptographic failures | Argon2id password hashes; TOTP secrets encrypted at rest (Fernet); secrets only in the environment. |
| A03 Injection | Every query goes through the ORM with bound parameters; search wildcards are escaped. |
| A05 Security misconfiguration | Request bodies reject unknown fields. Security headers (CSP, nosniff, frame denial, HSTS in production) are set. The API explorer is off in production. CORS allows only listed origins. |
| A07 Identification and authentication failures | Rate limits; 5 failures lock the account for 15 minutes; TOTP at sign-in; a fresh, single-use code at checkout; refresh-token rotation with reuse detection. |
| A09 Security logging and monitoring failures | Append-only audit log. A database trigger rejects UPDATE, DELETE and TRUNCATE. |

## Status against the fall MVP

Done:
- Accounts, email verification and TOTP.
- Listings with photos, browse and search.
- English auctions with sniping protection and live updates.
- Automatic closing.
- One transaction per sale, with a simulated checkout and step-up TOTP.
- Audit log and concurrency tests.

Spring 2027, not started:
- Dutch, sealed first-price and Vickrey strategies.
- Notifications beyond email.
- The admin dashboard (only `GET /api/admin/audit` exists).
- Flagging, and the full load and security evaluation.

Known gaps:
- Rate limits are counted per process; move them to Redis before running several API processes.
- Uploaded photos are checked by their first bytes but not re-encoded, so EXIF metadata is kept.
- Email delivery is opt-in through the Resend worker. Delivery to arbitrary recipients requires a verified sending domain.
- Base images are referenced by tag; pin them by digest before a public deployment.
- NFR-3 and NFR-4 are measured on a laptop only. One API process saturates near 100 bids a second with 4,000 watchers; the run on server hardware with two API processes is part of the spring evaluation.
