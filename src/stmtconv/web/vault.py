"""Dedicated authenticated encryption. Workspace/connection identity is bound as AAD."""

import base64
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from stmtconv.config import HostedSettings
from stmtconv.web.errors import WebError


class Vault:
    def __init__(self, config: HostedSettings):
        self.secret = config.ai_encryption_key

    def cipher(self) -> AESGCM:
        try:
            if self.secret is None:
                raise ValueError
            key = bytes.fromhex(self.secret.get_secret_value())
            if len(key) != 32:
                raise ValueError
            return AESGCM(key)
        except ValueError:
            raise WebError(
                503,
                "VAULT_UNAVAILABLE",
                "Secure key storage is not configured. Restore or configure the vault key in server settings.",
            ) from None

    @staticmethod
    def binding(workspace: UUID, connection: UUID) -> bytes:
        return f"dockling-byok-v1:{workspace}:{connection}".encode()

    def encrypt(self, workspace: UUID, connection: UUID, value: str) -> str:
        nonce = os.urandom(12)
        return base64.b64encode(
            nonce
            + self.cipher().encrypt(nonce, value.encode(), self.binding(workspace, connection))
        ).decode()

    def decrypt(self, workspace: UUID, connection: UUID, value: str) -> str:
        cipher = self.cipher()
        try:
            data = base64.b64decode(value, validate=True)
            return cipher.decrypt(
                data[:12], data[12:], self.binding(workspace, connection)
            ).decode()
        except Exception:
            raise WebError(
                503,
                "VAULT_INTEGRITY",
                "This connection key could not be opened. Restore the correct vault key or replace this connection's API key.",
            ) from None
