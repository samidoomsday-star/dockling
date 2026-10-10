"""Public HTTPS provider transport with DNS pinning, TLS checks and hard body limits."""

import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import cast
from urllib.parse import urlsplit

from stmtconv.ai.providers import Provider
from stmtconv.errors import StmtconvError

_DNS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="provider-dns")


def endpoint(value: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(r"[a-zA-Z0-9.-]+", host)
            or "." not in host
            or host.endswith((".local", ".internal", ".localhost"))
            or not re.fullmatch(r"/[a-zA-Z0-9/_-]*", parsed.path or "/")
            or ".." in parsed.path
            or "//" in parsed.path
        ):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError
        return host.lower(), parsed.path.rstrip("/")
    except ValueError:
        raise StmtconvError(
            "AI_ENDPOINT",
            "Use a public HTTPS provider endpoint on port 443 without credentials, query data or redirects.",
        ) from None


def public_addresses(host: str) -> list[str]:
    future = _DNS.submit(socket.getaddrinfo, host, 443, type=socket.SOCK_STREAM)
    try:
        records = future.result(timeout=5)
    except (TimeoutError, OSError):
        future.cancel()
        raise StmtconvError("AI_DNS", "The provider address could not be checked.") from None
    addresses = sorted({str(record[4][0]) for record in records})
    if (
        not addresses
        or len(addresses) > 20
        or any(not ipaddress.ip_address(a).is_global for a in addresses)
    ):
        raise StmtconvError("AI_ENDPOINT", "The provider must resolve only to public addresses.")
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str):
        self.tls_context = ssl.create_default_context()
        super().__init__(host, 443, timeout=10, context=self.tls_context)
        self.address = address

    def connect(self) -> None:
        raw = socket.create_connection((self.address, 443), timeout=10)
        try:
            self.sock = self.tls_context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class PublicTransport:
    def __init__(self, provider: Provider):
        self.provider = provider
        self.host, self.base_path = endpoint(provider.base_url)

    def request(
        self, method: str, route: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        if (
            method not in {"GET", "POST"}
            or not re.fullmatch(r"/[a-zA-Z0-9_/-]+", route)
            or "//" in route
        ):
            raise StmtconvError("AI_ENDPOINT", "Use a relative provider API route.")
        # Only a bounded GET can be retried automatically. POST uncertainty belongs
        # to the durable AI reservation ledger; this adapter never resends it.
        attempts = 2 if method == "GET" else 1
        for attempt in range(attempts):
            address = public_addresses(self.host)[0]
            client = PinnedHTTPS(self.host, address)
            try:
                headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
                if self.provider.api_key:
                    headers["Authorization"] = "Bearer " + self.provider.api_key.get_secret_value()
                body = (
                    json.dumps(payload, allow_nan=False).encode() if payload is not None else None
                )
                if body is not None:
                    if len(body) > 256 * 1024:
                        raise StmtconvError(
                            "AI_REQUEST_LIMIT", "The minimized provider request is too large."
                        )
                    headers["Content-Type"] = "application/json"
                deadline = time.monotonic() + 25
                client.request(method, self.base_path + route, body, headers)
                response = client.getresponse()
                if response.status in {429, 502, 503, 504} and attempt + 1 < attempts:
                    continue
                if response.status != 200:
                    raise StmtconvError(
                        "AI_HTTP",
                        "The provider declined the request. Check the endpoint, key and selected model; no settings were changed.",
                    )
                if response.getheader("Content-Encoding", "identity") != "identity":
                    raise StmtconvError("AI_RESPONSE_LIMIT", "Use a plain JSON provider response.")
                buffer = bytearray()
                while chunk := response.read(65536):
                    buffer.extend(chunk)
                    if len(buffer) > 2 * 1024**2 or time.monotonic() > deadline:
                        raise StmtconvError(
                            "AI_RESPONSE_LIMIT",
                            "The provider response exceeded its time/size limit.",
                        )
                value = json.loads(buffer)
                if not isinstance(value, dict):
                    raise ValueError
                return cast(dict[str, object], value)
            except StmtconvError:
                raise
            except Exception:
                raise StmtconvError(
                    "AI_CONNECTION",
                    "The provider connection could not be confirmed. Details are hidden.",
                ) from None
            finally:
                client.close()
        raise StmtconvError("AI_HTTP", "The provider is temporarily unavailable.")
