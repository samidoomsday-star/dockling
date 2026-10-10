"""Local synthetic browser test harness. No provider traffic, no production bypass flag."""

import json
from pathlib import Path

import uvicorn

from stmtconv.config import load_hosted_settings
from stmtconv.errors import StmtconvError
from stmtconv.web import connections
from stmtconv.web.app import create_app


class FictionalProvider:
    def request(
        self, method: str, route: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        if method == "GET" and route == "/models":
            return {
                "data": [
                    {
                        "id": "fictional-browser-ai",
                        "supported_reasoning_efforts": ["low", "high", "max"],
                    }
                ]
            }
        if (
            method != "POST"
            or route != "/chat/completions"
            or payload is None
            or payload.get("model") != "fictional-browser-ai"
        ):
            raise StmtconvError(
                "TEST_PROVIDER_ONLY",
                "Only the named fictional browser model is available in this harness.",
            )
        messages = payload["messages"]
        if not isinstance(messages, list) or not isinstance(messages[1], dict):
            raise ValueError
        content = str(messages[1]["content"]).split("Only transaction cells follow:\n", 1)[1]
        value = json.loads(content)
        return {"choices": [{"message": {"content": json.dumps(value)}}]}


def main() -> None:
    config = load_hosted_settings()
    if config.mode != "local" or config.base_url != "http://127.0.0.1:8000":
        raise SystemExit("This harness is restricted to the documented loopback synthetic setup.")

    def fake(provider):
        if (
            provider.base_url != "https://api.example.com/v1"
            or provider.selected_model != "fictional-browser-ai"
            or provider.requires_key
        ):
            raise StmtconvError(
                "TEST_PROVIDER_ONLY", "Configure the exact fictional no-key browser provider."
            )
        return FictionalProvider()

    connections.transport = fake
    app = create_app(config)
    app.state.broker.start(Path(".local-saas/broker/socket"))
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000, access_log=False)
    finally:
        app.state.broker.close()


if __name__ == "__main__":
    main()
