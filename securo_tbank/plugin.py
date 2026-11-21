"""Securo provider entrypoint."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable

from securo_tbank.client import InvestClient
from securo_tbank.errors import NeedsAuth
from securo_tbank.payload import build

INITIAL_HISTORY_DAYS = 365


def _token(context: Any) -> str:
    token = str((context.secrets or {}).get("token") or "").strip()
    if not token:
        raise NeedsAuth("T-Bank Invest API token is missing.")
    if len(token) > 4096:
        raise NeedsAuth("T-Bank Invest API token is too long.")
    return token


def sync_window(state: dict[str, Any], today: date) -> tuple[date, date] | None:
    end = today - timedelta(days=1)
    earliest = end - timedelta(days=INITIAL_HISTORY_DAYS - 1)
    last = state.get("last_report_end")
    start = date.fromisoformat(last) + timedelta(days=1) if last else earliest
    start = max(start, earliest)
    return None if start > end else (start, end)


class TBankInvest:
    def __init__(
        self,
        *,
        client_factory: Callable[[str], InvestClient] = InvestClient,
        today: Callable[[], date] = lambda: datetime.now(timezone.utc).date(),
    ) -> None:
        self._client_factory = client_factory
        self._today = today

    def sync(self, params: dict[str, Any], context: Any) -> dict[str, Any]:
        state = dict(params.get("state") or {})
        window = sync_window(state, self._today())
        if window is None:
            return {"state": state, "data": None}
        start, end = window
        client = self._client_factory(_token(context))
        brokerage_accounts = client.accounts()
        positions_by_account: dict[str, dict[str, Any]] = {}
        portfolios_by_account: dict[str, dict[str, Any]] = {}
        operations_by_account: dict[str, list[dict[str, Any]]] = {}
        instruments: dict[str, dict[str, Any]] = {}

        from_time = datetime.combine(start, time.min, tzinfo=timezone.utc).isoformat()
        to_time = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc).isoformat()
        for account in brokerage_accounts:
            account_id = str(account.get("id") or "")
            if not account_id:
                continue
            positions_by_account[account_id] = client.positions(account_id)
            portfolio = client.portfolio(account_id)
            portfolios_by_account[account_id] = portfolio
            operations = list(
                client.operations(account_id, from_time, to_time)
            )
            operations_by_account[account_id] = operations
            for position in portfolio.get("positions") or []:
                if not isinstance(position, dict):
                    continue
                uid = str(position.get("instrumentUid") or position.get("figi") or "")
                if uid and uid not in instruments:
                    instruments[uid] = client.instrument(uid)

        data = build(
            brokerage_accounts,
            positions_by_account,
            portfolios_by_account,
            operations_by_account,
            instruments,
        )
        state["last_report_end"] = end.isoformat()
        return {"state": state, "data": data}


plugin = TBankInvest()
