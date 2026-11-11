"""WebSocket watchers get a snapshot, then every committed bid (FR-32)."""

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from tests.conftest import make_account, make_auction


def test_watchers_get_a_snapshot_then_each_bid(settings) -> None:  # type: ignore[no-untyped-def]
    app = create_app(settings)
    with TestClient(app) as http:
        seller = http.portal.call(make_account, app, "seller")
        buyer = http.portal.call(make_account, app, "buyer")
        auction_id = http.portal.call(make_auction, app, seller)

        with http.websocket_connect(f"/ws/auctions/{auction_id}", headers={"origin": "http://localhost:5173"}) as socket:
            snapshot = socket.receive_json()
            assert snapshot["type"] == "snapshot" and snapshot["auction"]["bid_count"] == 0
            assert "viewer" not in snapshot["auction"]

            placed = http.post(f"/api/auctions/{auction_id}/bids", headers=buyer.headers, json={"amount": "100.00"})
            assert placed.status_code == 201, placed.text
            event = socket.receive_json()
            assert event["type"] == "bid_placed"
            assert (event["current_price"], event["bid_count"], event["leader_bidder_number"]) == ("100.00", 1, 1)


def test_other_sites_and_unknown_auctions_are_refused(settings) -> None:  # type: ignore[no-untyped-def]
    app = create_app(settings)
    with TestClient(app) as http:
        seller = http.portal.call(make_account, app, "seller")
        auction_id = http.portal.call(make_auction, app, seller)
        with pytest.raises(WebSocketDisconnect):
            with http.websocket_connect(f"/ws/auctions/{auction_id}", headers={"origin": "https://evil.example"}) as socket:
                socket.receive_json()
        with pytest.raises(WebSocketDisconnect):
            with http.websocket_connect("/ws/auctions/999999", headers={"origin": "http://localhost:5173"}) as socket:
                socket.receive_json()
