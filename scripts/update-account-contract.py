"""Refresh the implemented account contract from strict runtime models; retain earlier designs."""

import copy
from pathlib import Path

import yaml

from stmtconv.config import load_hosted_settings
from stmtconv.web.app import create_app


def update() -> None:
    path = Path("contracts/saas/openapi.yaml")
    doc = yaml.safe_load(path.read_text())
    app = create_app(load_hosted_settings())
    try:
        live = app.openapi()
    finally:
        app.state.engine.dispose()
    modules = {
        "WorkspaceCreate",
        "PlanCommand",
        "InvoiceCreate",
        "EvidenceCommand",
        "RequestCreate",
        "RequestUpdate",
        "AllowanceRead",
        "UsageRead",
        "PlanRead",
        "PlanList",
        "OffersRead",
        "InvoiceRead",
        "BillingRead",
        "AdminBillingRead",
        "RequestRead",
        "RequestsRead",
        "AdminRequestRead",
        "AdminRequestsRead",
        "InvitationRead",
        "InvitationsRead",
        "NoticeRead",
        "NoticesRead",
        "NoticeAcknowledged",
        "WorkspaceRead",
        "BillingWorkspaceRead",
        "BillingWorkspacesRead",
    }

    def rename(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k == "$ref" and isinstance(v, str) and v.startswith("#/components/schemas/"):
                    name = v.rsplit("/", 1)[1]
                    if name in modules:
                        value[k] = "#/components/schemas/HostedAccount" + name
                else:
                    rename(v)
        elif isinstance(value, list):
            for child in value:
                rename(child)

    for name in sorted(modules):
        doc["components"]["schemas"].pop("HostedAccount" + name, None)
    for name in sorted(modules):
        definition = copy.deepcopy(live["components"]["schemas"][name])
        rename(definition)
        doc["components"]["schemas"]["HostedAccount" + name] = definition
    inputs = {
        "/workspaces": ["post"],
        "/usage": ["get"],
        "/billing": ["get"],
        "/billing/checkout": ["post"],
        "/billing/portal": ["post"],
        "/plans": ["get"],
        "/invitations": ["get"],
        "/requests": ["get", "post"],
        "/notices": ["get"],
        "/notices/{notice}/read": ["post"],
        "/admin/plans": ["get", "post"],
        "/admin/billing-workspaces": ["get"],
        "/admin/workspaces/{workspace}/billing": ["get"],
        "/admin/workspaces/{workspace}/invoices": ["post"],
        "/admin/workspaces/{workspace}/invoices/{invoice}/evidence": ["post"],
        "/admin/requests": ["get"],
        "/admin/requests/{identifier}/response": ["post"],
    }
    for route, methods in inputs.items():
        for method in methods:
            operation = copy.deepcopy(live["paths"]["/api/v1" + route][method])
            rename(operation)
            operation["operationId"] = (
                "account_"
                + method
                + "_"
                + route.strip("/").replace("/", "_").replace("{", "").replace("}", "")
            )
            operation["x-phase"] = 5
            operation["x-implementation"] = (
                "implemented: manual-invoice pilot and synthetic local acceptance; live checkout/email remain disabled"
            )
            operation["x-workspace-scoped"] = route != "/workspaces"
            operation["x-access-roles"] = (
                ["platform_admin_mfa"]
                if route.startswith("/admin/")
                else ["owner"]
                if route in {"/billing", "/billing/checkout", "/billing/portal", "/invitations"}
                else ["member"]
                if route == "/workspaces"
                else ["owner", "editor", "viewer"]
            )
            operation["x-feature-ids"] = (
                ["N03"]
                if route in {"/workspaces", "/invitations"}
                else ["N08"]
                if "/requests" in route or "/notices" in route
                else ["F23", "N05"]
                if route == "/usage"
                else ["N05"]
            )
            if method != "get":
                operation.setdefault("parameters", []).extend(
                    [
                        {"$ref": "#/components/parameters/HeaderXCsrfToken"},
                        {"$ref": "#/components/parameters/HeaderIdempotencyKey"},
                    ]
                )
            for code in [400, 401, 403, 404, 409, 413, 422, 429, 503]:
                operation["responses"][str(code)] = {
                    "$ref": "#/components/responses/Error" + str(code)
                }
            if route in {"/billing/checkout", "/billing/portal"}:
                operation["responses"].pop("200", None)
                operation["summary"] = (
                    "Unavailable: manual invoices only; no hosted payment provider configured"
                )
            doc["paths"].setdefault(route, {})[method] = operation
    doc["info"]["version"] = "0.5.0"
    doc["info"]["description"] = (
        "Hosted Phases 1–5 support synthetic local acceptance with strict account reads, verified onboarding, conservative page/seat quotas, private notices/support and manual invoice evidence. Live checkout, email, commercial offers and deployment remain gated. Earlier future aliases retain their planned status."
    )
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


if __name__ == "__main__":
    update()
