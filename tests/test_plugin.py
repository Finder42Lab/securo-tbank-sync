from datetime import date
from types import SimpleNamespace

from securo_tbank.plugin import TBankInvest, sync_window


class FakeClient:
    token = ""

    def __init__(self, token):
        FakeClient.token = token

    def accounts(self):
        return [{"id": "acc-1", "name": "Брокерский"}]

    def positions(self, account_id):
        return {"money": [{"currency": "rub", "units": "50", "nano": 0}]}

    def portfolio(self, account_id):
        return {"positions": []}

    def operations(self, account_id, from_time, to_time):
        return iter(())

    def instrument(self, uid):
        raise AssertionError("No instruments expected")


def context():
    return SimpleNamespace(secrets={"token": "secret"}, config={})


def test_first_window_is_365_days_then_incremental():
    assert sync_window({}, date(2026, 11, 21)) == (
        date(2025, 11, 21),
        date(2026, 11, 20),
    )
    assert sync_window({"last_report_end": "2026-11-19"}, date(2026, 11, 21)) == (
        date(2026, 11, 20),
        date(2026, 11, 20),
    )


def test_sync_returns_provider_payload_and_state():
    plugin = TBankInvest(client_factory=FakeClient, today=lambda: date(2026, 11, 21))
    result = plugin.sync({"state": {}}, context())
    assert FakeClient.token == "secret"
    assert result["state"]["last_report_end"] == "2026-11-20"
    assert result["data"]["contract"] == 1
    assert result["data"]["accounts"][0]["balance"] == "50"
