"""Minimal standard-library client for T-Bank Invest REST API."""
from __future__ import annotations
from ssl import SSLContext
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

CERT = """-----BEGIN CERTIFICATE-----
MIIFwjCCA6qgAwIBAgICEAAwDQYJKoZIhvcNAQELBQAwcDELMAkGA1UEBhMCUlUx
PzA9BgNVBAoMNlRoZSBNaW5pc3RyeSBvZiBEaWdpdGFsIERldmVsb3BtZW50IGFu
ZCBDb21tdW5pY2F0aW9uczEgMB4GA1UEAwwXUnVzc2lhbiBUcnVzdGVkIFJvb3Qg
Q0EwHhcNMjIwMzAxMjEwNDE1WhcNMzIwMjI3MjEwNDE1WjBwMQswCQYDVQQGEwJS
VTE/MD0GA1UECgw2VGhlIE1pbmlzdHJ5IG9mIERpZ2l0YWwgRGV2ZWxvcG1lbnQg
YW5kIENvbW11bmljYXRpb25zMSAwHgYDVQQDDBdSdXNzaWFuIFRydXN0ZWQgUm9v
dCBDQTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAMfFOZ8pUAL3+r2n
qqE0Zp52selXsKGFYoG0GM5bwz1bSFtCt+AZQMhkWQheI3poZAToYJu69pHLKS6Q
XBiwBC1cvzYmUYKMYZC7jE5YhEU2bSL0mX7NaMxMDmH2/NwuOVRj8OImVa5s1F4U
zn4Kv3PFlDBjjSjXKVY9kmjUBsXQrIHeaqmUIsPIlNWUnimXS0I0abExqkbdrXbX
YwCOXhOO2pDUx3ckmJlCMUGacUTnylyQW2VsJIyIGA8V0xzdaeUXg0VZ6ZmNUr5Y
Ber/EAOLPb8NYpsAhJe2mXjMB/J9HNsoFMBFJ0lLOT/+dQvjbdRZoOT8eqJpWnVD
U+QL/qEZnz57N88OWM3rabJkRNdU/Z7x5SFIM9FrqtN8xewsiBWBI0K6XFuOBOTD
4V08o4TzJ8+Ccq5XlCUW2L48pZNCYuBDfBh7FxkB7qDgGDiaftEkZZfApRg2E+M9
G8wkNKTPLDc4wH0FDTijhgxR3Y4PiS1HL2Zhw7bD3CbslmEGgfnnZojNkJtcLeBH
BLa52/dSwNU4WWLubaYSiAmA9IUMX1/RpfpxOxd4Ykmhz97oFbUaDJFipIggx5sX
ePAlkTdWnv+RWBxlJwMQ25oEHmRguNYf4Zr/Rxr9cS93Y+mdXIZaBEE0KS2iLRqa
OiWBki9IMQU4phqPOBAaG7A+eP8PAgMBAAGjZjBkMB0GA1UdDgQWBBTh0YHlzlpf
BKrS6badZrHF+qwshzAfBgNVHSMEGDAWgBTh0YHlzlpfBKrS6badZrHF+qwshzAS
BgNVHRMBAf8ECDAGAQH/AgEEMA4GA1UdDwEB/wQEAwIBhjANBgkqhkiG9w0BAQsF
AAOCAgEAALIY1wkilt/urfEVM5vKzr6utOeDWCUczmWX/RX4ljpRdgF+5fAIS4vH
tmXkqpSCOVeWUrJV9QvZn6L227ZwuE15cWi8DCDal3Ue90WgAJJZMfTshN4OI8cq
W9E4EG9wglbEtMnObHlms8F3CHmrw3k6KmUkWGoa+/ENmcVl68u/cMRl1JbW2bM+
/3A+SAg2c6iPDlehczKx2oa95QW0SkPPWGuNA/CE8CpyANIhu9XFrj3RQ3EqeRcS
AQQod1RNuHpfETLU/A2gMmvn/w/sx7TB3W5BPs6rprOA37tutPq9u6FTZOcG1Oqj
C/B7yTqgI7rbyvox7DEXoX7rIiEqyNNUguTk/u3SZ4VXE2kmxdmSh3TQvybfbnXV
4JbCZVaqiZraqc7oZMnRoWrXRG3ztbnbes/9qhRGI7PqXqeKJBztxRTEVj8ONs1d
WN5szTwaPIvhkhO3CO5ErU2rVdUr89wKpNXbBODFKRtgxUT70YpmJ46VVaqdAhOZ
D9EUUn4YaeLaS8AjSF/h7UkjOibNc4qVDiPP+rkehFWM66PVnP1Msh93tc+taIfC
EYVMxjh8zNbFuoc7fzvvrFILLe7ifvEIUqSVIC/AzplM/Jxw7buXFeGP1qVCBEHq
391d/9RAfaZ12zkwFsl+IKwE/OZxW8AHa9i1p4GO0YSNuczzEm4=
-----END CERTIFICATE-----"""

Http = Callable[[str, dict[str, str], bytes, SSLContext], tuple[int, bytes]]


def urllib_post(url: str, headers: dict[str, str], body: bytes, ssl_context: SSLContext) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT, context=ssl_context) as response:
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

        self.context = ssl.create_default_context(cadata=CERT)

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
                self.context
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
