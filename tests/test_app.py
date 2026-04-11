import subprocess

import pytest
from fastapi.testclient import TestClient

from speedlog import app as app_module
from speedlog.app import app


def test_index_returns_html(tmp_data_dir):
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SPEEDLOG" in response.text


def test_api_data_no_csv(empty_data_dir):
    client = TestClient(app)
    response = client.get("/api/data")
    assert response.status_code == 200
    data = response.json()
    assert data["records"] == []
    assert data["stats"] == {}


def test_api_data_structure(csv_with_data):
    client = TestClient(app)
    response = client.get("/api/data")
    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert "stats" in data
    assert len(data["records"]) == 4


def test_api_stats_calculation(csv_with_data):
    client = TestClient(app)
    data = client.get("/api/data").json()
    stats = data["stats"]

    # 3 valid rows: download 300, 200, 400
    assert stats["download"]["avg"] == 300.0
    assert stats["download"]["min"] == 200.0
    assert stats["download"]["max"] == 400.0
    assert stats["download"]["latest"] == 400.0

    # ping 5, 8, 3
    assert stats["ping"]["avg"] == round((5.0 + 8.0 + 3.0) / 3, 2)
    assert stats["ping"]["min"] == 3.0
    assert stats["ping"]["max"] == 8.0

    # upload 50, 40, 60
    assert stats["upload"]["latest"] == 60.0


def test_api_error_counting(csv_with_data):
    client = TestClient(app)
    data = client.get("/api/data").json()
    stats = data["stats"]

    assert stats["total_tests"] == 4
    assert stats["successful_tests"] == 3
    assert stats["error_count"] == 1
    assert stats["error_rate_pct"] == 25.0


def test_api_server_distribution(csv_with_data):
    client = TestClient(app)
    data = client.get("/api/data").json()
    servers = data["stats"]["servers"]

    assert servers["Server A"] == 2
    assert servers["Server B"] == 1


def test_api_old_format_compat(csv_with_old_format):
    client = TestClient(app)
    data = client.get("/api/data").json()

    assert len(data["records"]) == 1
    record = data["records"][0]
    assert record["ping_ms"] == 7.0
    assert record["isp"] == ""
    assert record["server"] == ""


# --- /api/run-test ---


def _patch_resolve(monkeypatch, path="/fake/speedlog-collect"):
    from pathlib import Path

    monkeypatch.setattr(app_module, "_resolve_collect_script", lambda: Path(path))


def test_run_test_success(tmp_data_dir, monkeypatch):
    csv_path = tmp_data_dir / "speedtest_log.csv"
    csv_path.write_text("timestamp,ping_ms,download_mbit,upload_mbit,isp,server\n")

    def fake_run(cmd, **kwargs):
        with open(csv_path, "a") as f:
            f.write("2026-04-11 14:00:00,4.2,310.5,55.1,TM Net,Server X\n")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok line", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _patch_resolve(monkeypatch)

    client = TestClient(app)
    response = client.post("/api/run-test")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["record"]["download_mbit"] == 310.5
    assert body["record"]["server"] == "Server X"
    assert body["record"]["is_error"] is False


def test_run_test_failure(tmp_data_dir, monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="speedtest exploded")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _patch_resolve(monkeypatch)

    client = TestClient(app)
    response = client.post("/api/run-test")
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["error"] == "speedtest failed"
    assert "exploded" in detail["stderr"]


def test_run_test_timeout(tmp_data_dir, monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=120)

    monkeypatch.setattr(subprocess, "run", fake_run)
    _patch_resolve(monkeypatch)

    client = TestClient(app)
    response = client.post("/api/run-test")
    assert response.status_code == 504
    assert response.json()["detail"]["error"] == "speedtest timed out"


def test_run_test_concurrent_returns_409(tmp_data_dir, monkeypatch):
    _patch_resolve(monkeypatch)

    async def acquire_and_check():
        await app_module._run_test_lock.acquire()
        try:
            client = TestClient(app)
            response = client.post("/api/run-test")
            assert response.status_code == 409
            assert response.json()["detail"]["error"] == "test already in progress"
        finally:
            app_module._run_test_lock.release()

    import asyncio

    asyncio.new_event_loop().run_until_complete(acquire_and_check())


def test_run_test_script_not_found(tmp_data_dir, monkeypatch):
    def raise_missing():
        raise FileNotFoundError("nope")

    monkeypatch.setattr(app_module, "_resolve_collect_script", raise_missing)

    client = TestClient(app)
    response = client.post("/api/run-test")
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["error"] == "speedlog-collect not found"
    assert "hint" in detail
