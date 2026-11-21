"""Build Securo provider contract 1 payload."""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any

from securo_tbank.mapping import (
    TRADE_BUY_TYPES,
    asset_type,
    currency_of,
    decimal_value,
    is_trade,
    iso_date,
)

CONTRACT = 1
_PLACES = Decimal("0.00000001")
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


def number(value: Decimal) -> str:
    return format(value.quantize(_PLACES).normalize(), "f")


def build(
    brokerage_accounts: list[dict[str, Any]],
    positions_by_account: dict[str, dict[str, Any]],
    portfolios_by_account: dict[str, dict[str, Any]],
    operations_by_account: dict[str, list[dict[str, Any]]],
    instruments: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    accounts: list[dict[str, Any]] = []
    holdings: list[dict[str, Any]] = []

    for brokerage in brokerage_accounts:
        account_id = str(brokerage.get("id") or "")
        if not account_id:
            continue
        label = str(brokerage.get("name") or f"T-Bank {account_id[-4:]}")
        operations = operations_by_account.get(account_id, [])
        by_currency: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for operation in operations:
            if not is_trade(operation):
                by_currency[currency_of(operation.get("payment"))].append(operation)

        position_data = positions_by_account.get(account_id, {})
        money = position_data.get("money") or []
        currencies_seen: set[str] = set()
        for cash in money:
            if not isinstance(cash, dict):
                continue
            currency = currency_of(cash)
            currencies_seen.add(currency)
            accounts.append(
                _cash_account(account_id, label, currency, decimal_value(cash), by_currency[currency])
            )
        # Keep operations visible even when GetPositions omitted a zero cash balance.
        for currency, currency_operations in by_currency.items():
            if currency not in currencies_seen:
                accounts.append(
                    _cash_account(account_id, label, currency, Decimal("0"), currency_operations)
                )

        trade_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for operation in operations:
            if is_trade(operation):
                uid = str(operation.get("instrumentUid") or operation.get("figi") or "")
                if uid:
                    trade_map[uid].append(operation)

        portfolio = portfolios_by_account.get(account_id, {})
        for position in portfolio.get("positions") or []:
            if not isinstance(position, dict):
                continue
            uid = str(position.get("instrumentUid") or position.get("figi") or "")
            if not uid:
                continue
            holdings.append(
                _holding(account_id, position, instruments.get(uid, {}), trade_map.get(uid, []))
            )

    return {"contract": CONTRACT, "accounts": accounts, "holdings": holdings}


def _cash_account(
    account_id: str,
    label: str,
    currency: str,
    balance: Decimal,
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "external_id": f"tbank:{account_id}:{currency}",
        "name": f"{label} Cash ({currency})",
        "type": "investment",
        "balance": number(balance),
        "currency": currency,
        "masked_number": account_id[-4:],
        "transactions": [_transaction(account_id, operation, currency) for operation in operations],
    }


def _transaction(account_id: str, operation: dict[str, Any], currency: str) -> dict[str, Any]:
    operation_id = str(operation.get("id") or "")
    payment = decimal_value(operation.get("payment"))
    description = str(
        operation.get("description")
        or operation.get("name")
        or operation.get("type")
        or "T-Bank operation"
    )
    return {
        "external_id": f"tbank:{account_id}:operation:{operation_id}",
        "description": description[:500],
        "amount": number(abs(payment)),
        "date": iso_date(operation.get("date")),
        "type": "credit" if payment >= 0 else "debit",
        "currency": currency,
        "payee": "Т-Банк Инвестиции",
        "raw_data": operation,
    }


def _holding(
    account_id: str,
    position: dict[str, Any],
    instrument: dict[str, Any],
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    uid = str(position.get("instrumentUid") or position.get("figi"))
    quantity = decimal_value(position.get("quantity"))
    current_price = decimal_value(position.get("currentPrice"))
    average_price = decimal_value(
        position.get("averagePositionPriceFifo") or position.get("averagePositionPrice")
    )
    # Bond currentPrice does not include accrued coupon income (currentNkd).
    current_nkd = decimal_value(position.get("currentNkd"))
    value = quantity * (current_price + current_nkd)
    instrument_currency = str(instrument.get("currency") or "RUB").upper()
    currency = currency_of(
        position.get("currentPrice"),
        currency_of(position.get("averagePositionPriceFifo"), instrument_currency),
    )
    ticker = str(instrument.get("ticker") or position.get("ticker") or "")
    name = str(instrument.get("name") or ticker or f"T-Bank instrument {uid}")
    record: dict[str, Any] = {
        "external_id": f"tbank:{account_id}:{uid}",
        "name": name[:255],
        "type": asset_type(instrument, position),
        "currency": currency,
        "current_value": number(value),
        "quantity": number(quantity),
        "unit_price": number(current_price),
        "purchase_price": number(abs(average_price * quantity)),
        "ticker": ticker[:32] or None,
        "metadata": {
            "account_id": account_id,
            "instrument_uid": uid,
            "figi": position.get("figi"),
            "position_uid": position.get("positionUid"),
            "class_code": position.get("classCode"),
            "instrument_type": position.get("instrumentType"),
            "quantity_lots": (
                number(decimal_value(position.get("quantityLots")))
                if position.get("quantityLots") is not None
                else None
            ),
            "blocked": position.get("blocked"),
            "blocked_lots": (
                number(decimal_value(position.get("blockedLots")))
                if position.get("blockedLots") is not None
                else None
            ),
            "current_nkd": (
                number(current_nkd)
                if position.get("currentNkd") is not None
                else None
            ),
        },
        # Securo's trade ledger cannot represent short positions reliably.
        "trades": None if quantity < 0 else _trades(account_id, operations),
    }
    record["metadata"] = {
        key: value for key, value in record["metadata"].items() if value is not None
    }
    isin = str(instrument.get("isin") or "").upper()
    if _ISIN.fullmatch(isin):
        record["isin"] = isin
    return record


def _trades(
    account_id: str, operations: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Expand each operation into its exchange executions.

    GetOperationsByCursor returns aggregate operation values and, when
    available, individual executions in tradesInfo.trades. Securo needs the
    latter to preserve execution prices and dates.
    """
    result: list[dict[str, Any]] = []
    for operation in sorted(operations, key=lambda item: str(item.get("date") or "")):
        operation_id = str(operation.get("id") or operation.get("cursor") or "")
        info = operation.get("tradesInfo")
        executions = info.get("trades") if isinstance(info, dict) else None
        if isinstance(executions, list) and executions:
            commission = abs(decimal_value(operation.get("commission")))
            for index, execution in enumerate(executions):
                if not isinstance(execution, dict):
                    continue
                execution_id = str(execution.get("num") or index + 1)
                result.append(
                    _trade(
                        account_id,
                        operation,
                        execution,
                        f"{operation_id}:{execution_id}",
                        commission if index == 0 else Decimal("0"),
                    )
                )
        else:
            # Some operation types or older API responses contain only
            # aggregate quantity/price.
            result.append(
                _trade(
                    account_id,
                    operation,
                    operation,
                    operation_id,
                    abs(decimal_value(operation.get("commission"))),
                )
            )
    return result


def _trade(
    account_id: str,
    operation: dict[str, Any],
    execution: dict[str, Any],
    external_part: str,
    fee: Decimal,
) -> dict[str, Any]:
    payment = decimal_value(operation.get("payment"))
    quantity = abs(
        decimal_value(
            execution.get("quantity")
            or operation.get("quantityDone")
            or operation.get("quantity")
        )
    )
    price = abs(decimal_value(execution.get("price") or operation.get("price")))
    if not price and quantity:
        price = abs(payment) / quantity
    return {
        "external_id": f"tbank:{account_id}:trade:{external_part}",
        "kind": "buy" if operation.get("type") in TRADE_BUY_TYPES else "sell",
        "date": iso_date(execution.get("date") or operation.get("date")),
        "quantity": number(quantity),
        "price": number(price),
        "fee": number(fee),
    }
