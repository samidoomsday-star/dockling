"""Workspace vault, fake discovery, supported Max and SSRF boundaries; no paid calls."""

import json
import socket
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from stmtconv.ai.providers import Provider
from stmtconv.errors import StmtconvError
from stmtconv.web import connections
from stmtconv.web.egress import PublicTransport, endpoint, public_addresses
from stmtconv.web.errors import WebError
from stmtconv.web.models import Connection, Idempotency
from stmtconv.web.vault import Vault

BODY = {"name": "Fictional provider", "base_url": "https://api.example.com/v1"}
SECRET = "fake-key-not-a-real-provider-credential"


@pytest.fixture(autouse=True)
def no_live_provider(monkeypatch):
    from stmtconv.web.egress import PinnedHTTPS

    def blocked(_self):
        raise AssertionError("A test attempted live provider traffic")

    monkeypatch.setattr(PinnedHTTPS, "connect", blocked)


def create(c):
    r = c.post("/api/v1/connections", json=BODY)
    assert r.status_code == 201, r.text
    return r.json()


def write(c, path, version, **fields):
    c.headers["Idempotency-Key"] = str(uuid4())
    return c.post(path, json={"expected_revision": version, **fields})


class FakeProvider:
    def __init__(self, provider):
        assert provider.api_key.get_secret_value() == SECRET
        self.calls = []

    def request(self, method, route, payload=None):
        self.calls.append((method, route, payload))
        assert method == "GET" and route == "/models" and payload is None
        return {
            "data": [
                {"id": "fictional-max", "supported_reasoning_efforts": ["low", "high", "max"]},
                {"id": "fictional-unknown"},
            ]
        }


def test_keys_encrypted_bound_and_never_returned(world, monkeypatch):
    c = world["client"]("owner0")
    conn = create(c)
    path = "/api/v1/connections/" + conn["id"]
    response = c.put(path + "/key", json={"expected_revision": 1, "api_key": SECRET})
    assert response.status_code == 200, response.text
    assert response.json()["has_key"] and response.json()["version"] == 2
    assert SECRET not in response.text and "ciphertext" not in response.json()
    with Session(world["engine"]) as db:
        stored = db.get(Connection, UUID(conn["id"]))
        cipher = stored.ciphertext
        assert cipher != SECRET and SECRET not in cipher
        assert Vault(world["config"]).decrypt(stored.workspace_id, stored.id, cipher) == SECRET
        with pytest.raises(WebError, match="VAULT_INTEGRITY"):
            Vault(world["config"]).decrypt(world["workspaces"][1], stored.id, cipher)
        records = list(db.scalars(select(Idempotency)))
        assert SECRET not in json.dumps([r.response for r in records])
    for name in ["editor0", "viewer0", "owner1", "admin"]:
        other = world["client"](name)
        assert other.put(
            path + "/key", json={"expected_revision": 2, "api_key": SECRET}
        ).status_code == (403 if name in {"editor0", "viewer0"} else 404)
        assert other.get(path).status_code == (200 if name in {"editor0", "viewer0"} else 404)
        assert SECRET not in other.get(path).text
    assert (
        c.put(path + "/key", json={"expected_revision": 1, "api_key": "replacement"}).status_code
        == 409
    )
    response = write(c, path + "/revoke", 2)
    assert response.status_code == 200 and not response.json()["has_key"]
    with Session(world["engine"]) as db:
        assert db.get(Connection, UUID(conn["id"])).ciphertext is None


def test_fake_discovery_highest_supported_and_no_silent_downgrade(world, monkeypatch):
    c = world["client"]("owner0")
    record = create(c)
    path = "/api/v1/connections/" + record["id"]
    assert c.put(path + "/key", json={"expected_revision": 1, "api_key": SECRET}).status_code == 200
    fake = []

    def factory(p):
        f = FakeProvider(p)
        fake.append(f)
        return f

    monkeypatch.setattr(connections, "transport", factory)
    discovered = write(c, path + "/models", 2)
    assert discovered.status_code == 200, discovered.text
    assert fake[0].calls == [("GET", "/models", None)]
    assert discovered.json()["models"][1]["efforts"] == ["provider_default"]
    selected = write(c, path + "/selection", 3, model_id="fictional-max", effort="highest")
    assert selected.status_code == 200 and selected.json()["effort"] == "max"
    assert (
        write(c, path + "/selection", 4, model_id="fictional-unknown", effort="max").status_code
        == 422
    )
    assert c.get(path).json()["effort"] == "max"
    monkeypatch.setattr(FakeProvider, "request", lambda *args: {"data": [{"id": "fictional-max"}]})
    rediscovered = write(c, path + "/models", 4)
    assert rediscovered.status_code == 200 and rediscovered.json()["effort"] == "max"
    assert rediscovered.json()["test_code"] == "AI_EFFORT_UNSUPPORTED"
    manual = write(c, path + "/models/manual", 5, model_id="custom-model-id")
    assert manual.status_code == 200
    selected = write(c, path + "/selection", 6, model_id="custom-model-id", effort="highest")
    assert selected.status_code == 200 and selected.json()["effort"] == "provider_default"
    assert (
        write(
            c,
            path + "/terms",
            7,
            confirmed=True,
            terms_version="https://provider.example.com/terms/2026",
        ).status_code
        == 200
    )
    # Optional AI processing/consent is intentionally not enabled by connection setup.
    assert world["client"]("owner1").get("/api/v1/connections").json()["items"] == []


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/v1",
        "https://127.0.0.1/v1",
        "https://169.254.169.254/v1",
        "https://user:password@api.example.com/v1",
        "https://api.example.com:8080/v1",
        "https://api.example.com/v1?key=fake",
        "https://localhost/v1",
        "https://provider.internal/v1",
        "https://api.example.com/../v1",
        "https://api.example.com//v1",
    ],
)
def test_hosted_endpoint_policy_rejects_private_or_credential_urls(url):
    with pytest.raises(StmtconvError):
        endpoint(url)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "100.64.0.1",
    ],
)
def test_dns_private_and_mixed_answers_blocked(monkeypatch, address):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443)),
        ],
    )
    with pytest.raises(StmtconvError):
        public_addresses("api.example.com")


def test_public_transport_pins_address_and_refuses_redirects(monkeypatch):
    from stmtconv.web import egress

    monkeypatch.setattr(egress, "public_addresses", lambda host: ["93.184.216.34"])
    calls = []

    class FakeHTTPS:
        def __init__(self, host, address):
            calls.append((host, address))

        def request(self, method, path, body, headers):
            calls.append((method, path, headers.get("Authorization")))

        def getresponse(self):
            class Redirect:
                status = 302

            return Redirect()

        def close(self):
            pass

    monkeypatch.setattr(egress, "PinnedHTTPS", FakeHTTPS)
    with pytest.raises(StmtconvError):
        PublicTransport(Provider(name="fake", base_url=BODY["base_url"])).request("GET", "/models")
    assert calls == [("api.example.com", "93.184.216.34"), ("GET", "/v1/models", None)]


def test_connection_creation_replay_role_csrf_and_key_not_in_metadata(world):
    c = world["client"]("owner0")
    first = create(c)
    assert c.post("/api/v1/connections", json=BODY).json() == first
    assert world["client"]("editor0").post("/api/v1/connections", json=BODY).status_code == 403
    c.headers["X-CSRF-Token"] = "forged"
    assert (
        c.put(
            "/api/v1/connections/" + first["id"] + "/key",
            json={"expected_revision": 1, "api_key": SECRET},
        ).status_code
        == 403
    )
    assert (
        world["client"]("owner0").get("/api/v1/connections/" + first["id"]).json()["has_key"]
        is False
    )


def test_failed_discovery_preserves_catalog_and_vault_wrong_key_fails(world, monkeypatch):
    from pydantic import SecretStr

    c = world["client"]("owner0")
    record = create(c)
    path = "/api/v1/connections/" + record["id"]
    assert c.put(path + "/key", json={"expected_revision": 1, "api_key": SECRET}).status_code == 200
    monkeypatch.setattr(connections, "transport", FakeProvider)
    assert write(c, path + "/models", 2).status_code == 200
    before = c.get(path).json()

    def failed(*args):
        raise StmtconvError("AI_CONNECTION", "Provider unavailable")

    monkeypatch.setattr(FakeProvider, "request", failed)
    response = write(c, path + "/test", 3)
    assert response.status_code == 502 and SECRET not in response.text
    assert c.get(path).json() == before
    with Session(world["engine"]) as db:
        stored = db.get(Connection, UUID(record["id"]))
        wrong = world["config"].model_copy(update={"ai_encryption_key": SecretStr("11" * 32)})
        with pytest.raises(WebError, match="VAULT_INTEGRITY"):
            Vault(wrong).decrypt(stored.workspace_id, stored.id, stored.ciphertext)


def test_every_connection_mutation_denies_nonowners_and_foreign_members(world):
    record = create(world["client"]("owner0"))
    path = "/api/v1/connections/" + record["id"]
    commands = {
        "revoke": {},
        "models": {},
        "test": {},
        "models/manual": {"model_id": "fake"},
        "selection": {"model_id": "fake", "effort": "highest"},
        "terms": {"confirmed": True, "terms_version": "https://example.com/terms"},
    }
    for name in ("editor0", "viewer0", "owner1", "admin"):
        c = world["client"](name)
        for action, body in commands.items():
            response = write(c, path + "/" + action, 1, **body)
            assert response.status_code == (403 if name in {"editor0", "viewer0"} else 404)
    assert world["client"]("owner0").get(path).json()["version"] == 1


def test_invalid_key_never_echoed_by_validation(world):
    c = world["client"]("owner0")
    record = create(c)
    response = c.put(
        "/api/v1/connections/" + record["id"] + "/key",
        json={"expected_revision": 1, "api_key": SECRET + "\n"},
    )
    assert response.status_code == 422 and SECRET not in response.text


def test_provider_post_not_retried_and_response_size_bounded(monkeypatch):
    from stmtconv.web import egress

    monkeypatch.setattr(egress, "public_addresses", lambda host: ["93.184.216.34"])
    calls = []
    statuses = [503, 200]

    class FakeHTTPS:
        def __init__(self, host, address):
            pass

        def request(self, method, path, body, headers):
            calls.append(method)

        def getresponse(self):
            class Response:
                status = statuses.pop(0)

                def getheader(self, name, default=None):
                    return default

                def read(self, size):
                    return b"x" * size

            return Response()

        def close(self):
            pass

    monkeypatch.setattr(egress, "PinnedHTTPS", FakeHTTPS)
    transport = PublicTransport(Provider(name="fake", base_url=BODY["base_url"]))
    with pytest.raises(StmtconvError) as declined:
        transport.request("POST", "/chat/completions", {"model": "fake"})
    assert declined.value.code == "AI_HTTP"
    assert calls == ["POST"] and statuses == [200]
    with pytest.raises(StmtconvError) as oversized:
        transport.request("GET", "/models")
    assert oversized.value.code == "AI_RESPONSE_LIMIT"
    assert calls == ["POST", "GET"]
