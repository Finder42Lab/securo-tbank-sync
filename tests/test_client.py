import json

import pytest

from securo_tbank.client import API_BASE, InvestClient
from securo_tbank.errors import ApiTransient


class FakeHttp:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, body):
        self.calls.append((url, headers, json.loads(body)))
        return 200, json.dumps(self.responses.pop(0)).encode()


def test_get_accounts_uses_documented_route_and_bearer_token():
    http = FakeHttp({"accounts": [{"id": "acc-1", "name": "Брокерский"}]})
    accounts = InvestClient("secret-token", http=http).accounts()

    assert accounts == [{"id": "acc-1", "name": "Брокерский"}]
    url, headers, body = http.calls[0]
    assert url == (
        f"{API_BASE}/"
        "tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
    )
    assert headers["Authorization"] == "Bearer secret-token"
    assert body == {}


def test_operations_follow_cursor_until_has_next_is_false():
    http = FakeHttp(
        {
            "nextCursor": "page-2",
            "hasNext": True,
            "items": [{"id": "op-1"}],
        },
        {
            "nextCursor": "",
            "hasNext": False,
            "items": [{"id": "op-2"}],
        },
    )
    operations = list(
        InvestClient("token", http=http).operations(
            "acc-1", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"
        )
    )

    assert [operation["id"] for operation in operations] == ["op-1", "op-2"]
    assert http.calls[0][2]["accountId"] == "acc-1"
    assert http.calls[0][2]["cursor"] == ""
    assert http.calls[0][2]["limit"] == 1000
    assert http.calls[1][2]["cursor"] == "page-2"


def test_positions_loading_is_retried_instead_of_importing_partial_balance():
    client = InvestClient(
        "token",
        http=FakeHttp({"limitsLoadingInProgress": True, "money": []}),
    )
    with pytest.raises(ApiTransient, match="still calculating"):
        client.positions("acc-1")


def test_portfolio_requests_rubles_and_instrument_uses_uid():
    http = FakeHttp(
        {"accountId": "acc-1", "positions": []},
        {"instrument": {"uid": "uid-1", "ticker": "EXMP"}},
    )
    client = InvestClient("token", http=http)

    client.portfolio("acc-1")
    instrument = client.instrument("uid-1")

    assert http.calls[0][0].endswith(
        "OperationsService/GetPortfolio"
    )
    assert http.calls[0][2] == {"accountId": "acc-1", "currency": "RUB"}
    assert http.calls[1][0].endswith(
        "InstrumentsService/GetInstrumentBy"
    )
    assert http.calls[1][2] == {
        "idType": "INSTRUMENT_ID_TYPE_UID",
        "id": "uid-1",
    }
    assert instrument["ticker"] == "EXMP"
