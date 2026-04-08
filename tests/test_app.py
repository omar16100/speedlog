from fastapi.testclient import TestClient

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
