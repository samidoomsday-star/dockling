"""Validate the Phase 0 OpenAPI contract, examples and feature inventory offline."""

import json
import re
from hashlib import sha256
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "saas"
SCHEMA_HASH = "da01ba28852cac0de53893797cb8d1942bc3b05084f526dcc216717dec314ed0"
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def resolve(document, pointer):
    if not pointer.startswith("#/"):
        raise ValueError("Contract references must be local and resolvable offline")
    value = document
    for part in pointer[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def check():
    raw = (CONTRACT / "vendor" / "oas31-schema.json").read_bytes()
    if sha256(raw).hexdigest() != SCHEMA_HASH:
        raise ValueError("Official OpenAPI validation schema hash differs")
    document = yaml.safe_load((CONTRACT / "openapi.yaml").read_text())
    Draft202012Validator(json.loads(raw), format_checker=FormatChecker()).validate(document)
    for value in walk(document):
        if "$ref" in value:
            resolve(document, value["$ref"])
    schemas = document["components"]["schemas"]
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)

    source_text = (ROOT / "docs" / "WEB-APP-PLAN.md").read_text()
    section = source_text.split("## 6. Full existing-feature coverage map", 1)[1].split("## 7.", 1)[
        0
    ]
    source_rows = [
        line.split("|")[1].strip()
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("| Existing")
    ]
    inventory = json.loads((CONTRACT / "inventory-source.json").read_text())
    current_inventory = {f"F{i:02d}": row for i, row in enumerate(source_rows, 1)}
    if inventory != current_inventory or len(inventory) != 33:
        raise ValueError("Existing-feature inventory changed; remap coverage explicitly")
    matrix = (ROOT / "docs" / "saas" / "FEATURE-MATRIX.md").read_text()
    matrix_ids = re.findall(r"^\| (F\d{2}) ", matrix, flags=re.MULTILINE)
    if len(matrix_ids) != len(set(matrix_ids)) or set(matrix_ids) != set(inventory):
        raise ValueError("Feature matrix has missing or duplicate existing capabilities")

    ids, covered, operations = set(), set(), []
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            if method not in METHODS:
                continue
            if operation["operationId"] in ids:
                raise ValueError("Duplicate operation ID")
            ids.add(operation["operationId"])
            operations.append(operation)
            covered.update(operation["x-feature-ids"])
            parameters = [
                resolve(document, p["$ref"]) if "$ref" in p else p
                for p in operation.get("parameters", [])
            ]
            if not operation["x-access-roles"]:
                raise ValueError("Route missing a permission definition")
            names = {p["name"] for p in parameters if p["in"] == "path"}
            if names != set(re.findall(r"\{([^}]+)\}", path)):
                raise ValueError("Path parameter mismatch")
            if not isinstance(operation["x-workspace-scoped"], bool):
                raise ValueError("Route missing its workspace boundary")
            security = operation.get("security", document["security"])
            if "public" not in operation["x-access-roles"] and not security:
                raise ValueError("Private route has no security scheme")
            if method not in {"get", "head", "options"} and not path.startswith("/webhooks/"):
                headers = {p["name"]: p for p in parameters if p["in"] == "header"}
                if not headers.get("X-CSRF-Token", {}).get("required"):
                    raise ValueError("Session mutation missing mandatory CSRF header")
    if not set(inventory).issubset(covered):
        raise ValueError("OpenAPI does not map every existing feature")

    # Embed the schemas in each validator root so their local component refs work.
    checker = FormatChecker()
    manifest = json.loads((CONTRACT / "examples" / "manifest.json").read_text())
    for item in manifest:
        schema = {**schemas[item["schema"]], "components": document["components"]}
        validator = Draft202012Validator(schema, format_checker=checker)
        validator.validate(json.loads((CONTRACT / "examples" / item["file"]).read_text()))

    # Boundary probes check the useful promises of the schema, not API behavior.
    row_schema = {**schemas["Row"], "components": document["components"]}
    row = json.loads((CONTRACT / "examples" / "rows.json").read_text())["items"][0]
    for invalid in ({**row, "debit": 12.34}, {**row, "debit": "NaN"}):
        if Draft202012Validator(row_schema, format_checker=checker).is_valid(invalid):
            raise ValueError("Money schema accepted a float/nonfinite amount")
    connection = json.loads((CONTRACT / "examples" / "connection.json").read_text())
    if Draft202012Validator(
        {**schemas["Connection"], "components": document["components"]}
    ).is_valid({**connection, "api_key": "synthetic-secret-never-returned"}):
        raise ValueError("Connection read schema allows a credential field")
    review = json.loads((CONTRACT / "examples" / "review.json").read_text())
    review.pop("expected_revision")
    if Draft202012Validator(
        {**schemas["ReviewCommand"], "components": document["components"]}
    ).is_valid(review):
        raise ValueError("Review command accepts an absent expected revision")
    print(
        f"Validated {len(operations)} planned operations, {len(schemas)} schemas, "
        f"{len(manifest)} synthetic examples and all {len(inventory)} existing features."
    )
    print("No running API, tenant isolation, provider call or production readiness is implied.")


if __name__ == "__main__":
    check()
