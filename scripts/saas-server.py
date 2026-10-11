"""Single Linux API process for a separately provisioned synthetic staging host."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from stmtconv.config import HostedSettings, load_hosted_settings


def stage_config(path: Path) -> HostedSettings:
    from stmtconv.web.staging import private_file

    if not private_file(path):
        raise ValueError("Private configuration required")
    extra = path.parent / "ai-key.env"
    if path.name == "server.env" and (not private_file(extra)):
        raise ValueError("Matched private vault material required")
    config = load_hosted_settings(path)
    db = urlsplit(config.database_url.get_secret_value())
    if (
        config.mode != "production"
        or config.ai_dispatch_enabled
        or config.commercial_offers_enabled
        or not config.admin_subjects
        or config.ai_encryption_key is None
        or db.username != "dockling_app"
        or db.path != "/dockling_staging"
        or not config.s3_bucket.startswith("dockling-staging-")
    ):
        raise ValueError(
            "Use dedicated staging resources with inference and commercial offers paused"
        )
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--broker", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--synthetic-staging", action="store_true", required=True)
    args = parser.parse_args()
    try:
        import uvicorn

        from stmtconv.web.app import create_app
        from stmtconv.web.staging import database_check
        from stmtconv.web.storage import ObjectStore

        config = stage_config(args.config)
        if not 1024 <= args.port <= 65535:
            raise ValueError("Choose an unprivileged private port")
        if not args.broker.is_absolute() or args.broker.parent.is_symlink():
            raise ValueError("An explicit private broker directory is required")
        if not database_check(config) or not ObjectStore(config).healthy():
            raise ValueError("Provision verified database schema and storage before starting")
        app = create_app(config)
        app.state.broker.start(args.broker)
        try:
            # The selected host's HTTPS proxy owns public TLS. No public listener here.
            # One process owns the Unix broker. There is no multi-worker/reload option.
            uvicorn.run(
                app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False
            )
        finally:
            app.state.broker.close()
            app.state.engine.dispose()
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "code": "STAGING_STARTUP_CHECK_REQUIRED"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
