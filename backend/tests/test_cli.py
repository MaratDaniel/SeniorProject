"""The developer CLI. These tests replace the seeding itself, so they never touch a database."""

from pathlib import Path

import pytest

from app import cli

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
