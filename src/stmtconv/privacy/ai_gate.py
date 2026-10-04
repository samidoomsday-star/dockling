"""Every processing-time AI prerequisite is checked before creating a client."""

from dataclasses import dataclass

from stmtconv.errors import StmtconvError


@dataclass(frozen=True)
class Gate:
    activated: bool
    consent: str
    consent_note: str
    terms_confirmed: bool
    configured_model: bool
    credential_present: bool
    requires_key: bool
    pages_used: int
    page_cap: int


def check(gate: Gate, requested_pages: int) -> None:
    if not gate.activated or gate.consent != "granted" or not gate.consent_note.strip():
        raise StmtconvError(
            "AI_GATE_CLOSED",
            "AI requires explicit activation and recorded client consent with a note.",
        )
    if (
        not gate.terms_confirmed
        or not gate.configured_model
        or (gate.requires_key and not gate.credential_present)
    ):
        raise StmtconvError(
            "AI_GATE_CLOSED",
            "Confirm provider terms, select a model and configure required credentials.",
        )
    if requested_pages < 1 or gate.pages_used + requested_pages > gate.page_cap:
        raise StmtconvError("AI_PAGE_CAP", "The order's AI page budget would be exceeded.")
