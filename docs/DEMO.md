# Recording the demo

How to show the three demos of the final presentation (slides "Demo 1" to "Demo 3") on the running system, without waiting for a real auction to end.

## Before recording

1. Start the system and load fresh demo data. Seed right before recording: the first seeded auction ends 58 minutes later.

   ```bash
   cd backend
   tools/devdb.sh reset                    # empty database
   .venv/bin/alembic upgrade head
   .venv/bin/python -m app.cli seed-demo   # 8 auctions, 3 accounts in .demo-accounts.txt
   tools/run-api.sh                        # terminal 1
   cd ../frontend && npm run dev           # terminal 2, http://localhost:5173
   ```

2. Add the TOTP secrets of `buyer1@example.com` and `buyer2@example.com` from `backend/.demo-accounts.txt` to an authenticator app.
3. Open two browser windows side by side: buyer 1 in a normal window, buyer 2 in a private window, so each has its own session.
4. Keep http://localhost:5173/dev/mailbox open in a tab. Verification links arrive there.

## Demo 1: account security and a new listing (about 20 seconds)

1. **Create account** as "Buy and sell". Open the link from the dev mailbox, then sign in.
2. The security page shows the QR code. Scan it, type the code, and show the recovery codes.
3. **Sell**: title, photo, currency, starting price, a reserve price, the bid step. Point at the preview on the right ("Reserve price set. Bidders see whether it is met"), then **Publish auction**.

## Demo 2: live bidding from two browsers (about 30 seconds)

1. Open the same live auction in both windows, for example "Brass mantel clock".
2. Buyer 1 places the first preset. Window 1 shows **Winning**.
3. Buyer 2 bids. Window 1 turns to **Outbid** within a second, the price rolls to the new amount, and the bid history lists "Bidder 1" and "Bidder 2", never an email.

## Demo 3: closing and checkout (about 25 seconds)

1. Make the auction end in 30 seconds. The number is the auction id from the page address (`/auctions/1`):

   ```bash
   cd backend && .venv/bin/python -m app.cli close-in 1 --seconds 30
   ```

2. Reload both windows to show the new countdown. Do not bid again: a bid in the last two minutes extends the close by two minutes (sniping protection). To show that rule, bid once before running `close-in`, and say it.
3. At zero the auction closes by itself. The winner's window shows **You won this auction**, the other window **Closed**.
4. **Continue to checkout**: delivery details, then a fresh code from the authenticator app. The page ends on **Purchase complete** with the reference. **My account** lists the sale.

`close-in` works only in development (`ADAL_ENV=dev`) and writes an `auction.end_moved` entry to the audit log.

## Evidence on screen

- `cd backend && .venv/bin/pytest -q` runs the 50 tests in a few seconds.
- `.venv/bin/python -m tools.loadtest` prints the bid and delivery times for one busy auction in about ten seconds.
