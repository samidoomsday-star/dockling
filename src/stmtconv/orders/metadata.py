"""Read boundary shared by local manifests and hosted metadata, without web dependencies.

Legacy identifiers and hosted UUIDs remain distinct. Pipeline mutation migration is Phase 2.
"""

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from stmtconv.orders import store


class MetadataView(BaseModel):
    identifier: str
    name: str
    currency: str
    status: str


class MetadataReader[Identifier](Protocol):
    def describe(self, identifier: Identifier) -> MetadataView: ...


class LocalMetadata:
    def __init__(self, workspace: Path):
        self.workspace = workspace

    def describe(self, identifier: str) -> MetadataView:
        order = store.load(self.workspace, identifier)
        return MetadataView(
            identifier=order.order_id,
            name=order.client_alias,
            currency=order.currency,
            status=order.status,
        )
