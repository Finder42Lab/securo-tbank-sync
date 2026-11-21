from decimal import Decimal

from securo_tbank.mapping import decimal_value, is_trade
from securo_tbank.payload import build, number


def test_decimal_value_reads_units_and_nano():
    assert decimal_value({"units": "12", "nano": 340_000_000}) == Decimal("12.34")
    assert decimal_value({"units": "-12", "nano": -340_000_000}) == Decimal("-12.34")
    assert number(Decimal("1.123456789")) == "1.12345679"


def test_all_buy_sell_variants_are_trades():
    trade_types = {
        "OPERATION_TYPE_BUY",
        "OPERATION_TYPE_BUY_CARD",
        "OPERATION_TYPE_BUY_MARGIN",
        "OPERATION_TYPE_DELIVERY_BUY",
        "OPERATION_TYPE_PRIMARY_ORDER",
        "OPERATION_TYPE_SELL",
        "OPERATION_TYPE_SELL_CARD",
        "OPERATION_TYPE_SELL_MARGIN",
        "OPERATION_TYPE_DELIVERY_SELL",
    }
    assert all(is_trade({"type": item}) for item in trade_types)
    assert not is_trade({"type": "OPERATION_TYPE_DIVIDEND"})


def test_builds_cash_transactions_holding_and_trade():
    accounts = [{"id": "2000000001", "name": "ИИС"}]
    positions = {
        "2000000001": {
            "money": [{"currency": "rub", "units": "1000", "nano": 0}]
        }
    }
    portfolios = {
        "2000000001": {
            "positions": [
                {
                    "instrumentUid": "uid-1",
                    "figi": "BBG000",
                    "instrumentType": "share",
                    "quantity": {"units": "2", "nano": 0},
                    "currentPrice": {"currency": "rub", "units": "150", "nano": 0},
                    "currentNkd": {"currency": "rub", "units": "5", "nano": 0},
                    "averagePositionPriceFifo": {
                        "currency": "rub",
                        "units": "100",
                        "nano": 0,
                    },
                }
            ]
        }
    }
    operations = {
        "2000000001": [
            {
                "id": "div-1",
                "type": "OPERATION_TYPE_DIVIDEND",
                "description": "Дивиденды",
                "date": "2026-01-02T10:00:00Z",
                "payment": {"currency": "rub", "units": "10", "nano": 0},
            },
            {
                "id": "buy-1",
                "type": "OPERATION_TYPE_BUY",
                "date": "2026-01-01T10:00:00Z",
                "instrumentUid": "uid-1",
                "quantity": "2",
                "price": {"currency": "rub", "units": "100", "nano": 0},
                "payment": {"currency": "rub", "units": "-200", "nano": 0},
                "commission": {"currency": "rub", "units": "-1", "nano": 0},
                "tradesInfo": {
                    "trades": [
                        {
                            "num": "execution-1",
                            "date": "2026-01-01T10:00:01Z",
                            "quantity": "2",
                            "price": {
                                "currency": "rub",
                                "units": "100",
                                "nano": 0,
                            },
                        }
                    ]
                },
            },
        ]
    }
    instruments = {
        "uid-1": {
            "name": "Пример",
            "ticker": "EXMP",
            "isin": "RU0000000001",
            "instrumentType": "share",
        }
    }

    data = build(accounts, positions, portfolios, operations, instruments)

    assert data["contract"] == 1
    account = data["accounts"][0]
    assert account["external_id"] == "tbank:2000000001:RUB"
    assert account["balance"] == "1000"
    assert account["transactions"][0]["amount"] == "10"
    holding = data["holdings"][0]
    assert holding["external_id"] == "tbank:2000000001:uid-1"
    assert holding["current_value"] == "310"
    assert holding["trades"][0] == {
        "external_id": "tbank:2000000001:trade:buy-1:execution-1",
        "kind": "buy",
        "date": "2026-01-01",
        "quantity": "2",
        "price": "100",
        "fee": "1",
    }
