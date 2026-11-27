"""The developer CLI. The seed-demo tests replace the seeding itself, so they never touch a database."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app import cli
from app.db import db_now
from app.models import Auction, AuditLog
from tests.conftest import make_auction

ACCOUNT_LINE = "buyer  buyer1@example.com     password: pw   TOTP secret: SECRET"


async def fake_seed() -> list[str]:
    return [ACCOUNT_LINE]


async def must_not_seed() -> list[str]:
    raise AssertionError("seeded the database although the credentials could not be saved")


def test_seed_demo_stops_before_seeding_when_the_accounts_file_is_not_writable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The passwords exist only in that file: seeding first would lose them for good.
    monkeypatch.setattr(cli, "_seed_demo", must_not_seed)
    target = tmp_path / "missing-dir" / "accounts.txt"

    assert cli.main(["seed-demo", "--accounts-file", str(target)]) == 1
    assert "Cannot write" in capsys.readouterr().err
    assert not target.exists()


def test_seed_demo_writes_a_private_accounts_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_seed_demo", fake_seed)
    target = tmp_path / "accounts.txt"

    assert cli.main(["seed-demo", "--accounts-file", str(target)]) == 0
    assert ACCOUNT_LINE in target.read_text()
    assert target.stat().st_mode & 0o777 == 0o600


def test_seed_demo_prints_the_accounts_for_a_dash(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(cli, "_seed_demo", fake_seed)

    assert cli.main(["seed-demo", "--accounts-file", "-"]) == 0
    assert ACCOUNT_LINE in capsys.readouterr().out


@pytest.mark.anyio
async def test_close_in_moves_a_live_auction_to_its_end_in_development_only(app, settings, accounts) -> None:  # type: ignore[no-untyped-def]
    auction_id = await make_auction(app, await accounts("seller"), ends_in=timedelta(hours=1))

    with pytest.raises(SystemExit, match="ADAL_ENV=dev"):
        await cli._close_in(settings, auction_id, 30)  # the test settings are not a development environment

    await cli._close_in(settings.model_copy(update={"env": "dev"}), auction_id, 30)

    async with app.state.sessionmaker() as session:
        auction = await session.get(Auction, auction_id)
        now = await db_now(session)
        logged = await session.scalar(select(AuditLog.id).where(AuditLog.action == "auction.end_moved", AuditLog.target_id == auction_id))
    assert timedelta(seconds=25) < auction.ends_at - now <= timedelta(seconds=30)
    assert auction.original_ends_at == auction.ends_at and logged is not None
