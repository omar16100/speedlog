"""Speedlog dashboard — FastAPI backend serving CSV data and static HTML."""

import csv
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Speedlog Dashboard",
    root_path=os.environ.get("SPEEDLOG_ROOT_PATH", "/"),
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _csv_path() -> Path:
    """Resolve CSV path from env var. Called per-request for testability."""
    data_dir = Path(os.environ.get("SPEEDLOG_DATA_DIR", Path.home() / ".local/share/speedlog"))
    return data_dir / "speedtest_log.csv"


def _parse_row(row: list[str]) -> dict | None:
    """Parse a CSV row, handling both 4-col and 6-col formats. Returns None for short rows."""
    if len(row) < 4:
        return None

    timestamp = row[0]
    ping = row[1]
    download = row[2]
    upload = row[3]
    isp = row[4] if len(row) > 4 else ""
    server = row[5] if len(row) > 5 else ""

    is_error = ping == "ERROR"

    return {
        "timestamp": timestamp,
        "ping_ms": None if is_error else float(ping),
        "download_mbit": None if is_error else float(download),
        "upload_mbit": None if is_error else float(upload),
        "isp": isp,
        "server": server,
        "is_error": is_error,
    }


@app.get("/")
async def index():
    logger.info("Serving dashboard index")
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/data")
async def get_data():
    """Return all speedtest records as JSON."""
    csv_path = _csv_path()

    if not csv_path.exists():
        logger.warning("CSV file not found: %s", csv_path)
        return {"records": [], "stats": {}}

    records = []
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            parsed = _parse_row(row)
            if parsed:
                records.append(parsed)

    logger.info("Loaded %d records from %s", len(records), csv_path)

    valid = [r for r in records if not r["is_error"]]
    total = len(records)
    errors = total - len(valid)

    stats = {}
    if valid:
        downloads = [r["download_mbit"] for r in valid]
        uploads = [r["upload_mbit"] for r in valid]
        pings = [r["ping_ms"] for r in valid]

        stats = {
            "total_tests": total,
            "successful_tests": len(valid),
            "error_count": errors,
            "error_rate_pct": round(errors / total * 100, 1) if total > 0 else 0,
            "download": {
                "avg": round(sum(downloads) / len(downloads), 2),
                "min": round(min(downloads), 2),
                "max": round(max(downloads), 2),
                "latest": round(downloads[-1], 2),
            },
            "upload": {
                "avg": round(sum(uploads) / len(uploads), 2),
                "min": round(min(uploads), 2),
                "max": round(max(uploads), 2),
                "latest": round(uploads[-1], 2),
            },
            "ping": {
                "avg": round(sum(pings) / len(pings), 2),
                "min": round(min(pings), 2),
                "max": round(max(pings), 2),
                "latest": round(pings[-1], 2),
            },
            "servers": {},
            "isp": valid[-1]["isp"] if valid[-1]["isp"] else "Unknown",
        }

        for r in valid:
            s = r["server"] or "Unknown"
            stats["servers"][s] = stats["servers"].get(s, 0) + 1

    return {"records": records, "stats": stats}


def main():
    """Entry point for `speedlog-dashboard` console script."""
    import uvicorn

    host = os.environ.get("SPEEDLOG_HOST", "127.0.0.1")
    port = int(os.environ.get("SPEEDLOG_PORT", "8080"))
    logger.info("Starting speedlog dashboard on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
