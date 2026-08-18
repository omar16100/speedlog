"""Speedlog dashboard — FastAPI backend serving CSV data and static HTML."""

import asyncio
import csv
import logging
import os
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
BUNDLED_COLLECT_SCRIPT = Path(__file__).parent.parent.parent / "bin" / "speedlog-collect"
# Must exceed the collector's worst case: a first attempt that hangs until
# Ookla's own timeout, plus SPEEDLOG_RETRY_DELAY (60s default), plus a full
# second measurement. At 120s the retry could never finish, and the SIGKILL
# that followed would destroy a measurement mid-flight and leak its temp file.
RUN_TEST_TIMEOUT_SECONDS = 300

app = FastAPI(
    title="Speedlog Dashboard",
    root_path=os.environ.get("SPEEDLOG_ROOT_PATH", "/"),
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_run_test_lock = asyncio.Lock()


def _resolve_collect_script() -> Path:
    """Locate speedlog-collect: PATH first, then bundled dev copy."""
    found = shutil.which("speedlog-collect")
    if found:
        return Path(found)
    if BUNDLED_COLLECT_SCRIPT.exists():
        return BUNDLED_COLLECT_SCRIPT
    raise FileNotFoundError("speedlog-collect not found on PATH or bundled location")


def _csv_path() -> Path:
    """Resolve CSV path from env var. Called per-request for testability."""
    data_dir = Path(os.environ.get("SPEEDLOG_DATA_DIR", Path.home() / ".local/share/speedlog"))
    return data_dir / "speedtest_log.csv"


# Failures we positively identified as the measurement tool's fault.
#
# "unknown" is deliberately NOT in this set. Legacy rows written before the
# status column all parse as "unknown", and counting them here would assert a
# cause that was never recorded, which is the exact misattribution this column
# exists to prevent. They are reported separately as unclassified.
TOOL_ERROR_STATUSES = {
    "config_unavailable",
    "no_servers",
    "connect_timeout",
    "parse_error",
}


def _parse_row(row: list[str]) -> dict | None:
    """Parse a CSV row, handling the 4-col, 6-col and 8-col formats. Returns None for short rows."""
    if len(row) < 4:
        return None

    timestamp = row[0]
    ping = row[1]
    download = row[2]
    upload = row[3]
    isp = row[4] if len(row) > 4 else ""
    server = row[5] if len(row) > 5 else ""
    server_id = row[7] if len(row) > 7 else ""

    # Anything non-numeric is treated as a failed row rather than allowed to
    # raise. One malformed row would otherwise take down the whole /api/data
    # response, turning a single bad sample into a dead dashboard.
    try:
        ping_val = float(ping)
        download_val = float(download)
        upload_val = float(upload)
        is_error = False
    except ValueError:
        ping_val = download_val = upload_val = None
        is_error = True

    # Rows written before the status column carry no classification. Treat a
    # legacy failure as "unknown" rather than inventing a cause for it.
    if len(row) > 6 and row[6]:
        status = row[6]
    else:
        status = "unknown" if is_error else "ok"

    return {
        "timestamp": timestamp,
        "ping_ms": ping_val,
        "download_mbit": download_val,
        "upload_mbit": upload_val,
        "isp": isp,
        "server": server,
        "server_id": server_id,
        "status": status,
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
            # Failures broken out by cause. A raw error rate conflates "the
            # line was down" with "Ookla would not answer", and in practice
            # the second dominates.
            "status_counts": {},
            "tool_error_count": sum(
                1 for r in records if r["status"] in TOOL_ERROR_STATUSES
            ),
            # Failures with no recorded cause: legacy rows, or classes the
            # collector did not recognise. Reported on their own so nobody
            # reads them as evidence either way.
            "unclassified_error_count": sum(
                1 for r in records if r["is_error"] and r["status"] == "unknown"
            ),
            "retry_recovered_count": sum(
                1 for r in records if r["status"] == "ok_retry"
            ),
        }

        for r in records:
            st = r["status"] or "unknown"
            stats["status_counts"][st] = stats["status_counts"].get(st, 0) + 1

        for r in valid:
            s = r["server"] or "Unknown"
            stats["servers"][s] = stats["servers"].get(s, 0) + 1

    return {"records": records, "stats": stats}


def _read_last_record() -> dict | None:
    csv_path = _csv_path()
    if not csv_path.exists():
        return None
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        last = None
        for row in reader:
            parsed = _parse_row(row)
            if parsed:
                last = parsed
    return last


@app.post("/api/run-test")
async def run_test():
    """Trigger speedlog-collect on demand and return the resulting CSV row."""
    if _run_test_lock.locked():
        logger.info("on-demand test rejected: another test in progress")
        raise HTTPException(status_code=409, detail={"error": "test already in progress"})

    async with _run_test_lock:
        try:
            script_path = _resolve_collect_script()
        except FileNotFoundError as e:
            logger.error("speedlog-collect not found: %s", e)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "speedlog-collect not found",
                    "hint": "install speedlog (uv pip install -e .) or place script on PATH",
                },
            )

        logger.info("Running on-demand speedtest via %s", script_path)

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [str(script_path)],
                capture_output=True,
                text=True,
                timeout=RUN_TEST_TIMEOUT_SECONDS,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            logger.error("on-demand speedtest timed out after %ds", RUN_TEST_TIMEOUT_SECONDS)
            raise HTTPException(status_code=504, detail={"error": "speedtest timed out"})

        if result.returncode != 0:
            stderr_tail = (result.stderr or "")[-500:]
            logger.error("on-demand speedtest failed (rc=%d): %s", result.returncode, stderr_tail)
            raise HTTPException(
                status_code=500,
                detail={"error": "speedtest failed", "stderr": stderr_tail},
            )

        record = _read_last_record()
        logger.info("on-demand test ok: %s", result.stdout.strip())
        return {"status": "ok", "record": record, "stdout": result.stdout.strip()}


def main():
    """Entry point for `speedlog-dashboard` console script."""
    import uvicorn

    host = os.environ.get("SPEEDLOG_HOST", "127.0.0.1")
    port = int(os.environ.get("SPEEDLOG_PORT", "8080"))
    logger.info("Starting speedlog dashboard on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
