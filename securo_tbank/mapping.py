"""Map T-Bank API values to provider-neutral records."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

TRADE_BUY_TYPES = {
    "OPERATION_TYPE_BUY",
    "OPERATION_TYPE_BUY_CARD",
    "OPERATION_TYPE_BUY_MARGIN",
    "OPERATION_TYPE_DELIVERY_BUY",
    "OPERATION_TYPE_PRIMARY_ORDER",
}
TRADE_SELL_TYPES = {
    "OPERATION_TYPE_SELL",
    "OPERATION_TYPE_SELL_CARD",
    "OPERATION_TYPE_SELL_MARGIN",
    "OPERATION_TYPE_DELIVERY_SELL",
}

ASSET_TYPES = {
    "share": "stock",
    "etf": "etf",
    "bond": "investment",
    "future": "investment",
    "option": "investment",
    "currency": "investment",
}


def decimal_value(value: Any) -> Decimal:
    """Convert Quotation/MoneyValue or scalar into Decimal."""
    if isinstance(value, dict):
        units = value.get("units", "0")
        nano = value.get("nano", 0)
        try:
            return Decimal(str(units)) + Decimal(str(nano)) / Decimal("1000000000")
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("0")
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def currency_of(value: Any, fallback: str = "RUB") -> str:
    if isinstance(value, dict):
        currency = str(value.get("currency") or "").upper()
        if len(currency) == 3 and currency.isalpha():
            return currency
    return fallback


def iso_date(value: Any) -> str:
    raw = str(value or "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return raw[:10]


def is_trade(operation: dict[str, Any]) -> bool:
    kind = str(operation.get("type") or "")
    return kind in TRADE_BUY_TYPES or kind in TRADE_SELL_TYPES


def asset_type(instrument: dict[str, Any], position: dict[str, Any]) -> str:
    kind = str(
        instrument.get("instrumentType")
        or position.get("instrumentType")
        or ""
    ).lower()
    return ASSET_TYPES.get(kind, "investment")
