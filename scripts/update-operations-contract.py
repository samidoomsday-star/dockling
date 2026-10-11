"""Refresh Phase 6 strict read contracts without replacing future design boundaries."""

import copy
from pathlib import Path

import yaml

from stmtconv.config import load_hosted_settings
from stmtconv.web.app import create_app


def update():
    path = Path("contracts/saas/openapi.yaml")
    doc = yaml.safe_load(path.read_text())
    app = create_app(load_hosted_settings())
    try:
        live = app.openapi()
    finally:
        app.state.engine.dispose()
    names = {"Signal", "OperationsRead", "ComponentRead"}

    def rename(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "$ref" and isinstance(child, str) and child.rsplit("/", 1)[-1] in names:
                    value[key] = "#/components/schemas/HostedOps" + child.rsplit("/", 1)[-1]
                else:
                    rename(child)
        elif isinstance(value, list):
            for child in value:
                rename(child)

    for name in sorted(names):
        definition = copy.deepcopy(live["components"]["schemas"][name])
        rename(definition)
        doc["components"]["schemas"]["HostedOps" + name] = definition
    for route in ["/admin/operations", "/health/live", "/health/ready"]:
        op = copy.deepcopy(live["paths"]["/api/v1" + route]["get"])
        rename(op)
        op["operationId"] = "ops_get_" + route.strip("/").replace("/", "_")
        op["x-phase"] = 6
        op["x-implementation"] = (
            "implemented: anonymous component/status reads; independent and hosted release review remain gated"
        )
        op["x-feature-ids"] = ["F30", "N09"]
        op["x-workspace-scoped"] = False
        op["x-access-roles"] = ["platform_admin_mfa"] if route.startswith("/admin/") else ["public"]
        if not route.startswith("/admin/"):
            op["security"] = []
        for code in [401, 403, 404, 429, 503]:
            op["responses"][str(code)] = {"$ref": "#/components/responses/Error" + str(code)}
        if route == "/health/ready":
            op["responses"]["503"] = {
                "description": "One or more required components unavailable",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/HostedOpsComponentRead"}
                    }
                },
            }
        doc["paths"][route] = {"get": op}
    doc["info"]["version"] = "0.6.0"
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


if __name__ == "__main__":
    update()
