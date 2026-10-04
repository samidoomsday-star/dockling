import json
import logging

from hypothesis import given
from hypothesis import strategies as st

from stmtconv.logging_setup import configure_logging, redact_text


def test_log_file_and_console_hide_private_fields(tmp_path, capsys):
    logger = configure_logging(tmp_path, "INFO")
    logger.info(
        "account 123456789012; merchant %(description)s",
        {"description": "Synthetic Private Merchant"},
        extra={
            "details": {
                "name": "Private Buyer",
                "api_key": "private-test-key",
                "nested": {"raw_text": "private raw statement"},
            }
        },
    )
    for handler in logging.getLogger().handlers:
        handler.flush()
    text = (tmp_path / "logs/stmtconv.log").read_text()
    console = capsys.readouterr().out
    for private in [
        "123456789012",
        "Synthetic Private Merchant",
        "Private Buyer",
        "private-test-key",
        "private raw statement",
    ]:
        assert private not in text + console
    assert "********9012" in text
    payload = json.loads(text.splitlines()[-1])
    assert payload["context"]["details"]["nested"]["raw_text"] == "[REDACTED]"


def test_exception_text_and_existing_handler_are_redacted(tmp_path, caplog):
    logger = configure_logging(tmp_path, "INFO")
    try:
        raise ValueError("PRIVATE EXCEPTION CONTENT 123456789012")
    except ValueError:
        logger.exception("Operation failed", extra={"description": "Private Description"})
    text = (tmp_path / "logs/stmtconv.log").read_text()
    assert "PRIVATE EXCEPTION CONTENT" not in text + caplog.text
    assert "Private Description" not in text
    assert json.loads(text)["context"]["error_type"] == "ValueError"


def test_reinitialization_does_not_duplicate_records(tmp_path):
    configure_logging(tmp_path, "INFO")
    logger = configure_logging(tmp_path, "INFO")
    logger.info("one event")
    assert len((tmp_path / "logs/stmtconv.log").read_text().splitlines()) == 1


@given(st.text(alphabet="0123456789", min_size=8, max_size=24))
def test_long_digit_runs_are_masked(number):
    masked = redact_text(number)
    assert masked == "*" * (len(number) - 4) + number[-4:]
