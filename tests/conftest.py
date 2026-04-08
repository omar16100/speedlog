import os

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Set SPEEDLOG_DATA_DIR to a temp directory and return the path."""
    monkeypatch.setenv("SPEEDLOG_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def csv_with_data(tmp_data_dir):
    """Create a CSV with mixed valid/error/4-col rows. Returns the CSV path."""
    csv_path = tmp_data_dir / "speedtest_log.csv"
    csv_path.write_text(
        "timestamp,ping_ms,download_mbit,upload_mbit,isp,server\n"
        "2026-04-07 10:00:00,5.0,300.0,50.0,TM Net,Server A\n"
        "2026-04-07 11:00:00,ERROR,ERROR,ERROR,ERROR,ERROR\n"
        "2026-04-07 12:00:00,8.0,200.0,40.0,TM Net,Server B\n"
        "2026-04-07 13:00:00,3.0,400.0,60.0,TM Net,Server A\n"
    )
    return csv_path


@pytest.fixture
def csv_with_old_format(tmp_data_dir):
    """Create a CSV with old 4-col format rows."""
    csv_path = tmp_data_dir / "speedtest_log.csv"
    csv_path.write_text(
        "timestamp,ping_ms,download_mbit,upload_mbit\n"
        "2026-04-03 22:00:00,7.0,300.0,55.0\n"
    )
    return csv_path


@pytest.fixture
def empty_data_dir(tmp_data_dir):
    """SPEEDLOG_DATA_DIR set but no CSV file exists."""
    return tmp_data_dir
