import pytest

from speedlog.app import _parse_row


def test_valid_8col_row():
    row = [
        "2026-08-18 15:00:00", "5.5", "307.9", "52.4",
        "TM Net", "Server A", "ok", "12345",
    ]
    result = _parse_row(row)
    assert result["download_mbit"] == 307.9
    assert result["status"] == "ok"
    assert result["server_id"] == "12345"
    assert result["is_error"] is False


def test_retry_status_is_not_an_error():
    row = [
        "2026-08-18 15:00:00", "5.5", "307.9", "52.4",
        "TM Net", "Server A", "ok_retry", "12345",
    ]
    result = _parse_row(row)
    assert result["status"] == "ok_retry"
    assert result["is_error"] is False


@pytest.mark.parametrize(
    "status", ["config_unavailable", "no_servers", "connect_timeout", "unknown"]
)
def test_classified_tool_errors(status):
    row = [
        "2026-08-18 15:00:00", "ERROR", "ERROR", "ERROR",
        "ERROR", "ERROR", status, "",
    ]
    result = _parse_row(row)
    assert result["is_error"] is True
    assert result["status"] == status
    assert result["ping_ms"] is None


def test_legacy_error_row_defaults_to_unknown_status():
    """Rows written before the status column must not claim a cause they never recorded."""
    row = ["2026-04-07 11:00:00", "ERROR", "ERROR", "ERROR", "ERROR", "ERROR"]
    assert _parse_row(row)["status"] == "unknown"


def test_legacy_success_row_defaults_to_ok_status():
    row = ["2026-04-07 10:00:00", "5.0", "300.0", "50.0", "TM Net", "Server A"]
    result = _parse_row(row)
    assert result["status"] == "ok"
    assert result["server_id"] == ""


def test_legacy_4col_row_has_no_status_column():
    row = ["2026-04-03 22:00:00", "7.0", "300.0", "55.0"]
    result = _parse_row(row)
    assert result["status"] == "ok"
    assert result["server_id"] == ""


def test_empty_status_field_falls_back():
    """An 8-col row with a blank status is treated as legacy, not as a status named ''."""
    row = [
        "2026-08-18 15:00:00", "5.5", "307.9", "52.4",
        "TM Net", "Server A", "", "",
    ]
    assert _parse_row(row)["status"] == "ok"


def test_valid_6col_row():
    row = ["2026-04-07 10:00:00", "5.0", "300.0", "50.0", "TM Net", "Server A"]
    result = _parse_row(row)
    assert result["timestamp"] == "2026-04-07 10:00:00"
    assert result["ping_ms"] == 5.0
    assert result["download_mbit"] == 300.0
    assert result["upload_mbit"] == 50.0
    assert result["isp"] == "TM Net"
    assert result["server"] == "Server A"
    assert result["is_error"] is False


def test_valid_4col_row():
    row = ["2026-04-03 22:00:00", "7.0", "300.0", "55.0"]
    result = _parse_row(row)
    assert result["ping_ms"] == 7.0
    assert result["isp"] == ""
    assert result["server"] == ""
    assert result["is_error"] is False


def test_error_row():
    row = ["2026-04-07 11:00:00", "ERROR", "ERROR", "ERROR", "ERROR", "ERROR"]
    result = _parse_row(row)
    assert result["is_error"] is True
    assert result["ping_ms"] is None
    assert result["download_mbit"] is None
    assert result["upload_mbit"] is None


def test_short_row_returns_none():
    assert _parse_row(["2026-04-07 10:00:00", "5.0"]) is None
    assert _parse_row([]) is None


def test_zero_values():
    row = ["2026-04-07 10:00:00", "0.0", "0.0", "0.0", "ISP", "Server"]
    result = _parse_row(row)
    assert result["ping_ms"] == 0.0
    assert result["download_mbit"] == 0.0
    assert result["is_error"] is False


def test_large_values():
    row = ["2026-04-07 10:00:00", "999.99", "10000.0", "5000.0", "ISP", "Server"]
    result = _parse_row(row)
    assert result["download_mbit"] == 10000.0
    assert result["upload_mbit"] == 5000.0
