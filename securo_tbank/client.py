"""Minimal standard-library client for T-Bank Invest REST API."""
from __future__ import annotations
import ssl

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any

from securo_tbank.errors import ApiTransient, NeedsAuth

API_BASE = "https://invest-public-api.tbank.ru/rest"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
HTTP_TIMEOUT = 30
APP_NAME = "securo-tbank"

Http = Callable[[str, dict[str, str], bytes], tuple[int, bytes]]


def urllib_post(url: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        # Never expose an upstream body: it may contain request details.
        payload = b""
        exc.close()
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ApiTransient("T-Bank API response is larger than 20 MB.")
    return status, payload


class InvestClient:
    def __init__(self, token: str, *, http: Http = urllib_post) -> None:
        self._token = token
        self._http = http

        context = ssl.create_default_context()

        context.load_cert_chain(
            certfile="Russian_Trusted_Root_CA.cer",
        )

    def _call(self, service: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{API_BASE}/tinkoff.public.invest.api.contract.v1.{service}/{method}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-app-name": APP_NAME,
        }
        try:
            status, raw = self._http(
                url,
                headers,
                json.dumps(payload, separators=(",", ":")).encode(),
            )
        except OSError as exc:
            raise ApiTransient(f"Could not reach T-Bank API ({type(exc).__name__}).") from None
        if status in (401, 403):
            raise NeedsAuth("T-Bank rejected the API token. Create a read-only token and reconnect.")
        if status == 429 or status >= 500:
            raise ApiTransient(f"T-Bank API is temporarily unavailable (HTTP {status}).")
        if status != 200:
            raise ApiTransient(f"T-Bank API returned HTTP {status}.")
        try:
            result = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiTransient("T-Bank API returned unreadable JSON.") from None
        if not isinstance(result, dict):
            raise ApiTransient("T-Bank API returned an unexpected response.")
        return result

    def accounts(self) -> list[dict[str, Any]]:
        response = self._call("UsersService", "GetAccounts", {})
        accounts = response.get("accounts") or []
        if not isinstance(accounts, list):
            raise ApiTransient("T-Bank API returned an invalid account list.")
        return [
            account
            for account in accounts
            if isinstance(account, dict)
            and account.get("status") in (None, "ACCOUNT_STATUS_OPEN")
            and account.get("accessLevel") not in ("ACCOUNT_ACCESS_LEVEL_NO_ACCESS",)
        ]

    def positions(self, account_id: str) -> dict[str, Any]:
        response = self._call(
            "OperationsService", "GetPositions", {"accountId": account_id}
        )
        if response.get("limitsLoadingInProgress") is True:
            raise ApiTransient(
                "T-Bank is still calculating account positions. Try again later."
            )
        return response

    def portfolio(self, account_id: str) -> dict[str, Any]:
        return self._call(
            "OperationsService",
            "GetPortfolio",
            {"accountId": account_id, "currency": "RUB"},
        )

    def operations(
        self, account_id: str, from_time: str, to_time: str
    ) -> Iterator[dict[str, Any]]:
        cursor = ""
        while True:
            response = self._call(
                "OperationsService",
                "GetOperationsByCursor",
                {
                    "accountId": account_id,
                    "from": from_time,
                    "to": to_time,
                    "state": "OPERATION_STATE_EXECUTED",
                    "withoutCommissions": False,
                    "withoutTrades": False,
                    "withoutOvernights": True,
                    "limit": 1000,
                    "cursor": cursor,
                },
            )
            for item in response.get("items") or []:
                if isinstance(item, dict):
                    yield item
            if not response.get("hasNext"):
                return
            next_cursor = response.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor:
                raise ApiTransient("T-Bank API returned an invalid operations cursor.")
            cursor = next_cursor

    def instrument(self, uid: str) -> dict[str, Any]:
        response = self._call(
            "InstrumentsService",
            "GetInstrumentBy",
            {"idType": "INSTRUMENT_ID_TYPE_UID", "id": uid},
        )
        instrument = response.get("instrument") or {}
        return instrument if isinstance(instrument, dict) else {}
