"""Deterministic OFX 1.02 SGML, with occurrence-aware FITIDs and escaped text."""

import hashlib
from collections import Counter
from html import escape

from stmtconv.core.models import Statement
from stmtconv.errors import StmtconvError


def serialize(statement: Statement, created_at: str) -> bytes:
    summary = statement.summary
    if (
        summary.period_start is None
        or summary.period_end is None
        or summary.closing is None
        or summary.account_mask is None
    ):
        raise StmtconvError(
            "OFX_SUMMARY", "OFX requires period, masked account and closing balance."
        )
    if summary.account_key is None:
        raise StmtconvError(
            "OFX_ACCOUNT_ID",
            "OFX requires a private account identity or an explicitly confirmed account group.",
        )
    card = summary.direction == "liability"
    messages = "CREDITCARDMSGSRSV1" if card else "BANKMSGSRSV1"
    response = "CCSTMTTRNRS" if card else "STMTTRNRS"
    statement_tag = "CCSTMTRS" if card else "STMTRS"
    account_tag = "CCACCTFROM" if card else "BANKACCTFROM"
    lines = [
        "OFXHEADER:100",
        "DATA:OFXSGML",
        "VERSION:102",
        "SECURITY:NONE",
        "ENCODING:USASCII",
        "CHARSET:1252",
        "COMPRESSION:NONE",
        "OLDFILEUID:NONE",
        "NEWFILEUID:NONE",
        "",
        "<OFX>",
        "<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS>",
        f"<DTSERVER>{created_at}<LANGUAGE>ENG</SONRS></SIGNONMSGSRSV1>",
        f"<{messages}><{response}><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS>",
        f"<{statement_tag}><CURDEF>{summary.currency}",
        f"<{account_tag}><ACCTID>{escape(summary.account_mask)}"
        + ("<BANKID>UNKNOWN<ACCTTYPE>CHECKING" if not card else "")
        + f"</{account_tag}>",
        f"<BANKTRANLIST><DTSTART>{summary.period_start:%Y%m%d}<DTEND>{summary.period_end:%Y%m%d}",
    ]
    occurrences: Counter[str] = Counter()
    for row in statement.transactions:
        if row.date is None or "AMOUNT_UNPARSABLE" in row.flags:
            raise StmtconvError("OFX_ROW", "OFX cannot contain an unknown date or amount.")
        key = f"{summary.account_key or summary.account_mask}|{row.date.isoformat()}|{row.amount:.2f}|{' '.join(row.description.split())}"
        occurrence = occurrences[key]
        occurrences[key] += 1
        fitid = hashlib.sha256(f"{key}|{occurrence}".encode()).hexdigest()[:16]
        lines.extend(
            [
                "<STMTTRN>",
                f"<TRNTYPE>{'DEBIT' if row.amount < 0 else 'CREDIT'}",
                f"<DTPOSTED>{row.date:%Y%m%d}",
                f"<TRNAMT>{row.amount:.2f}",
                f"<FITID>{fitid}",
                f"<NAME>{escape(row.description[:32])}",
                f"<MEMO>{escape(row.description)}",
                "</STMTTRN>",
            ]
        )
    lines.extend(
        [
            "</BANKTRANLIST>",
            f"<LEDGERBAL><BALAMT>{summary.closing:.2f}<DTASOF>{summary.period_end:%Y%m%d}</LEDGERBAL>",
            f"</{statement_tag}></{response}></{messages}>",
            "</OFX>",
        ]
    )
    return ("\r\n".join(lines) + "\r\n").encode("cp1252", errors="xmlcharrefreplace")
