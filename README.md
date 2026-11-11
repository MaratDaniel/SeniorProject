# Adal: online auction service (senior project, fall 2026)

An online auction service where bidding stays correct when many people bid at once: one winner and one price, every time.

| File | What it is |
|---|---|
| `Adal-presentation.html` | Final deck, one self-contained file (19 slides, ~6 min). Open in a browser; arrows / space / click to move. |
| `Adal-report.html` | End-of-term report, one self-contained file. |
| `design/` | Web screens for the frontend team: landing, browse, auction page with bidding states, sign-in and two-step, create listing, checkout. Open `design/index.html`. See `design/README.md`. |
| `brandbook/` | Brandbook sources (design canvas). Live copy: https://claude.ai/artifact/DdaGY8GP3Qj1Bvi1aNEJrX |
| `DESIGN.md` | Design tokens and rules. |
| `PRODUCT.md` | Product context. |
| `Online_Auction_Service_Requirements_and_Design_v2.docx` | Requirements and design (source of truth). |
| `backend/`, `frontend/` | The working system: FastAPI back end and React front end. How to run it is below. |
| `docs/SYSTEM_DESIGN.md` | How the system works, with the full database schema. |
| `docs/API.md` | The API contract between the front end and the back end. |
| `docker-compose.yml` | The whole stack with one command. |

Fonts load from Google Fonts, so the deck needs internet for exact typography.

## Still to fill in
Usability and design scores, two Security cells (sector slide); method name, chat tool, sync time, team lead; course calendar dates; real test numbers.

## Stack

| Part | Choice |
|---|---|
| Front end | React 19, TypeScript, Vite, React Router |
| API | FastAPI (Python 3.13), Pydantic |
| Live updates | WebSockets in FastAPI, fan-out through Redis pub/sub across processes (in memory when Redis is not configured) |
| Database | PostgreSQL with SQLAlchemy 2 and Alembic; row-level locking for bids |
| Accounts | Argon2id passwords, short-lived JWT access tokens, rotating refresh token in an httpOnly cookie, TOTP (pyotp) at sign-in and again at checkout |
| Packaging | Docker Compose: PostgreSQL, Redis, migrations, API, scheduler worker, nginx |

> The design document v2 proposed Django + DRF + Channels. The backend here is FastAPI; the database design, locking, strategy pattern and WebSocket events are the same. Open issue #1 in the document (the stack) still needs the advisor's sign-off.

## Layout

```
backend/
  app/
    engine/        auction engine: base.py (strategy interface), english.py, service.py (locking, close)
    realtime/      WebSocket endpoint and the event broker
    routers/       auth, listings, auctions, transactions, admin, dev
    security/      passwords, tokens, TOTP, rate limiting
    models.py      schema; migrations/ holds the Alembic migration
    scheduler.py   opens, closes and expires on time (also runs as app/worker.py)
  tests/           34 tests, including the concurrency tests
  tools/devdb.sh   local PostgreSQL without Docker
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
.venv/bin/python -m app.cli seed-demo # optional: demo accounts in .demo-accounts.txt, 4 auctions
tools/run-api.sh                      # http://127.0.0.1:8000, API explorer at /api/docs
```

Front end (Node 22.22 or later):

```bash
cd frontend
npm ci
npm run dev                           # http://localhost:5173
```

Email is not delivered in development: verification and reset links appear at http://localhost:5173/dev/mailbox. The demo accounts already have two-step sign-in; add each TOTP secret from `.demo-accounts.txt` to an authenticator app.

## Run it with Docker

```bash
cp .env.example .env    # then fill in the three secrets
docker compose up --build
```

Open http://localhost:8080. To add demo data and print the demo accounts: `docker compose run --rm api python -m app.cli seed-demo --accounts-file -`.

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
- **The database enforces the invariants.** There is one auction per listing, one transaction per auction (unique keys) and one bidder number per bidder. Money is `numeric(12,2)`, never a float.
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
- Email is queued in a table, not sent.
- Base images are referenced by tag; pin them by digest before a public deployment.
- No load test yet for NFR-3 and NFR-4 (Locust or k6).
