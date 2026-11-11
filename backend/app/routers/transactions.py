"""Sales and checkout with a step-up code (FR-5, FR-34 to FR-36, NFR-6, UC-8)."""

import secrets

from fastapi import APIRouter, Request
from sqlalchemy import or_, select

from app import audit
from app.db import db_now
from app.deps import CurrentUser, LimiterDep, SessionDep, SettingsDep, client_ip
from app.errors import ApiError, not_found
from app.mail import queue_email
from app.models import Auction, Listing, Transaction, TransactionStatus, User
from app.schemas import ConfirmIn, TransactionOut
from app.security.totp import SecretBox, match_step
from app.views import images_for, media_url, transaction_out

router = APIRouter(prefix="/api/transactions", tags=["checkout"])


async def _view(session, tx: Transaction, viewer_id: int) -> TransactionOut:  # type: ignore[no-untyped-def]
    auction = await session.get(Auction, tx.auction_id)
    listing = await session.get(Listing, auction.listing_id)
    images = (await images_for(session, [listing.id]))[listing.id]
    cover = media_url(images[0].storage_key) if images else None
    return transaction_out(tx, auction, listing, cover, viewer_id)


@router.get("", response_model=list[TransactionOut])
async def list_transactions(user: CurrentUser, session: SessionDep) -> list[TransactionOut]:
    rows = await session.scalars(
        select(Transaction)
        .where(or_(Transaction.buyer_id == user.id, Transaction.seller_id == user.id))  # only your own sales
        .order_by(Transaction.created_at.desc())
        .limit(200)
    )
    return [await _view(session, tx, user.id) for tx in rows]


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_transaction(transaction_id: int, user: CurrentUser, session: SessionDep) -> TransactionOut:
    tx = await session.get(Transaction, transaction_id)
    if tx is None or user.id not in (tx.buyer_id, tx.seller_id):
        raise not_found("This purchase does not exist.")  # 404, not 403: do not confirm that it exists
    return await _view(session, tx, user.id)


@router.post("/{transaction_id}/confirm", response_model=TransactionOut)
async def confirm(
    transaction_id: int, body: ConfirmIn, request: Request, user: CurrentUser, session: SessionDep, settings: SettingsDep, limiter: LimiterDep
) -> TransactionOut:
    limiter.check(f"confirm:{user.id}", 10, 60)
    ip = client_ip(request)
    error: ApiError | None = None
    async with session.begin():
        tx = (
            await session.execute(
                select(Transaction).where(Transaction.id == transaction_id).with_for_update().execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if tx is None or tx.buyer_id != user.id:
            raise not_found("This purchase does not exist.")
        buyer = (
            await session.execute(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
        ).scalar_one()
        now = await db_now(session)
        if tx.status == TransactionStatus.PENDING and tx.expires_at <= now:
            tx.status = TransactionStatus.EXPIRED  # the scheduler would do this on its next tick anyway
            audit.record(session, "transaction.expired", target_type="transaction", target_id=tx.id)
        if tx.status == TransactionStatus.EXPIRED:
            error = ApiError(410, "transaction_expired", "The time to complete this purchase has passed.")
        elif tx.status != TransactionStatus.PENDING:
            error = ApiError(409, "transaction_not_pending", "This purchase is already complete.")
        elif not buyer.mfa_enabled or buyer.mfa_secret_enc is None:
            error = ApiError(403, "mfa_required", "Turn on two-step sign-in to complete a purchase.")
        else:
            secret = SecretBox(settings.mfa_encryption_key.get_secret_value()).open(buyer.mfa_secret_enc)
            step = match_step(secret, body.code)
            if step is None or (buyer.mfa_last_step is not None and step <= buyer.mfa_last_step):
                # A fresh code is required even inside a signed-in session; a used code never works twice.
                audit.record(session, "transaction.code_rejected", actor_id=user.id, target_type="transaction", target_id=tx.id, ip=ip)
                error = ApiError(400, "invalid_code", "That code is not right or has expired. Your purchase is not complete.")
            else:
                buyer.mfa_last_step = step
                tx.status = TransactionStatus.COMPLETED
                tx.completed_at = now
                tx.payment_ref = f"SIM-{secrets.token_hex(6).upper()}"  # simulated payment: no money moves (DR-10)
                tx.delivery = body.delivery.model_dump()
                audit.record(
                    session, "transaction.completed", actor_id=user.id, target_type="transaction", target_id=tx.id, ip=ip, data={"payment_ref": tx.payment_ref}
                )
                auction = await session.get(Auction, tx.auction_id)
                listing = await session.get(Listing, auction.listing_id)  # type: ignore[union-attr]
                seller = await session.get(User, tx.seller_id)
                reference = f"TX-{tx.id:06d}"
                queue_email(
                    session,
                    to=buyer.email,
                    subject=f"Purchase complete: {listing.title}",  # type: ignore[union-attr]
                    body=f"Your purchase of \"{listing.title}\" for {tx.amount:.2f} is complete. Reference {reference}. Nothing was charged in this version.\n",  # type: ignore[union-attr]
                )
                queue_email(
                    session,
                    to=seller.email,  # type: ignore[union-attr]
                    subject=f"Ready to deliver: {listing.title}",  # type: ignore[union-attr]
                    body=f"The buyer completed checkout for \"{listing.title}\". Reference {reference}. Delivery details are on the sale page.\n",  # type: ignore[union-attr]
                )
    if error is not None:
        raise error
    return await _view(session, tx, user.id)
