"""Verified service TLS; explicit private CAs never disable certificate/host checks."""

import ssl

from stmtconv.config import HostedSettings, WorkerSettings


def service_tls(config: HostedSettings | WorkerSettings) -> ssl.SSLContext:
    return ssl.create_default_context(cafile=config.tls_ca_file)
