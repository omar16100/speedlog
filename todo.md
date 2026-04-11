# speedlog todo

## 2026-04-11
- Added `POST /api/run-test` endpoint in `src/speedlog/app.py` — subprocesses `bin/speedlog-collect`, asyncio lock, 120s timeout, returns parsed last CSV row.
- Added `RUN TEST` button in `src/speedlog/static/index.html` header (HTML + CSS + JS handler). Calls `/api/run-test`, refreshes dashboard on success, handles 409 (in-progress) and failures.
- Added 5 pytest tests in `tests/test_app.py`: success, failure, timeout, concurrent-409, script-not-found. All 18 tests pass.
- Switched live launchd service from `/Users/macmini/projects/speedtest-dashboard/app.py` to canonical speedlog package via `~/Library/LaunchAgents/com.speedlog.dashboard.plist`. New env: `SPEEDLOG_DATA_DIR=/Users/macmini/logs`, `SPEEDLOG_HOST=0.0.0.0`, `SPEEDLOG_PORT=8050`, `SPEEDLOG_ROOT_PATH=/speedtest`, `SPEEDTEST_BIN=/opt/homebrew/bin/speedtest`, PATH includes `/opt/homebrew/bin` for jq.
- Symlinked `bin/speedlog-collect` into `.venv/bin/` so `shutil.which` finds it.
- End-to-end verified: real speedtest ran via `curl -X POST http://127.0.0.1:8050/api/run-test`, row landed in `/Users/macmini/logs/speedtest_log.csv`.

## Backlog
- `pyproject.toml` does not ship `bin/speedlog-collect` as a console script — the symlink workaround works for editable installs but breaks for `pip install speedlog` from PyPI. Either bundle as data file + entry point, or document install.sh as the only supported install path.
- Old `/Users/macmini/projects/speedtest-dashboard/` fork is now unused — can be deleted after a few days of stable speedlog operation.
- `_run_test_lock` only protects in-process; cron collector at `/Users/macmini/scripts/speedtest_monitor.sh` could collide on simultaneous CSV writes. Low risk; mitigate with file lock if it surfaces.
