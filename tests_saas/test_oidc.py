"""Authlib's verifier against a signed test issuer; no fake login HTTP endpoint."""

import asyncio
import time

import pytest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey

from stmtconv.web.auth import oauth_client


@pytest.mark.parametrize("bad", ["signature", "issuer", "audience", "nonce", "expired"])
def test_oidc_signed_claims_reject_tampering(configs, monkeypatch, bad):
    config = configs[0]
    key = RSAKey.generate_key(2048)
    identity = oauth_client(config)

    async def metadata():
        return {"issuer": config.oidc_issuer, "id_token_signing_alg_values_supported": ["RS256"]}

    async def keys(force=False):
        return {"keys": [key.as_dict(private=False)]}

    monkeypatch.setattr(identity, "load_server_metadata", metadata)
    monkeypatch.setattr(identity, "fetch_jwk_set", keys)
    now = int(time.time())
    claims = {
        "iss": config.oidc_issuer,
        "sub": "synthetic",
        "aud": config.oidc_client_id,
        "exp": now + 60,
        "iat": now,
        "nonce": "expected-nonce",
    }
    valid = jwt.encode({"alg": "RS256"}, claims, key)
    assert (
        asyncio.run(
            identity.parse_id_token(
                {"id_token": valid, "access_token": "synthetic"}, nonce="expected-nonce"
            )
        )["sub"]
        == "synthetic"
    )
    signer = key
    if bad == "signature":
        signer = RSAKey.generate_key(2048)
    if bad == "issuer":
        claims["iss"] = "https://wrong.example"
    if bad == "audience":
        claims["aud"] = "wrong-client"
    if bad == "nonce":
        claims["nonce"] = "wrong-nonce"
    if bad == "expired":
        claims["exp"] = now - 300
    token = jwt.encode({"alg": "RS256"}, claims, signer)
    with pytest.raises(JoseError):
        asyncio.run(
            identity.parse_id_token(
                {"id_token": token, "access_token": "synthetic"},
                nonce="expected-nonce",
                leeway=30,
                claims_options={
                    "iss": {"essential": True, "value": config.oidc_issuer},
                    "aud": {"essential": True, "value": config.oidc_client_id},
                    "exp": {"essential": True},
                },
            )
        )
