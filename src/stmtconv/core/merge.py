"""Pure continuity analysis; never conceal missing periods or mixed accounts."""

from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, Field

from stmtconv.core.models import Statement


class MergeIssue(BaseModel):
    code: str
    statement_id: str
    difference: Decimal | None = None


class MergeResult(BaseModel):
    statements: list[Statement]
    issues: list[MergeIssue] = Field(default_factory=list)


def merge(
    statements: list[Statement], tolerance: Decimal, operator_group: str | None = None
) -> MergeResult:
    ordered = sorted(
        statements, key=lambda s: (s.summary.period_start is None, s.summary.period_start)
    )
    result = MergeResult(statements=ordered)
    if (
        any(s.summary.account_mask is None for s in ordered)
        or len({(s.summary.account_mask, s.summary.currency, s.summary.direction) for s in ordered})
        != 1
    ):
        result.issues.append(MergeIssue(code="ACCOUNT_GROUP_UNKNOWN", statement_id="all"))
    keys = {s.summary.account_key for s in ordered if s.summary.account_key}
    if len(keys) > 1:
        result.issues.append(MergeIssue(code="ACCOUNT_GROUP_UNKNOWN", statement_id="all"))
    elif any(s.summary.account_key is None for s in ordered) and not operator_group:
        result.issues.append(MergeIssue(code="ACCOUNT_IDENTITY_UNCONFIRMED", statement_id="all"))
    for previous, current in zip(ordered, ordered[1:], strict=False):
        before, after = previous.summary, current.summary
        if before.period_end is None or after.period_start is None:
            result.issues.append(MergeIssue(code="PERIOD_UNKNOWN", statement_id=current.id))
        elif after.period_start > before.period_end + timedelta(days=1):
            result.issues.append(MergeIssue(code="PERIOD_GAP", statement_id=current.id))
        elif after.period_start <= before.period_end:
            result.issues.append(MergeIssue(code="PERIOD_OVERLAP", statement_id=current.id))
        if before.closing is None or after.opening is None:
            result.issues.append(MergeIssue(code="CONTINUITY_UNKNOWN", statement_id=current.id))
        elif abs(after.opening - before.closing) > tolerance:
            result.issues.append(
                MergeIssue(
                    code="CONTINUITY_GAP",
                    statement_id=current.id,
                    difference=after.opening - before.closing,
                )
            )
    return result
