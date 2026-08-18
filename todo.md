# speedlog todo

## 2026-08-18

Analysed 136 days / 3,109 rows of live data and fixed what it exposed. Branch `fix/collector-error-classification`.

- CSV schema 6 → 8 columns: added `status` and `server_id`. `_parse_row` handles 4/6/8-col rows; legacy failures report `unknown` rather than a fabricated cause.
- `speedlog-collect` classifies Ookla failures (`config_unavailable`, `no_servers`, `connect_timeout`, `unknown`) instead of collapsing everything to `ERROR`. The old behaviour made a 12.5% error rate look like ISP downtime when it was Ookla's endpoints (39.2% failures at 00:00 local vs 5-13% elsewhere).
- Retry once after `SPEEDLOG_RETRY_DELAY` (60s default), recorded as `ok_retry` so recovery stays measurable. 111 of 164 historical error streaks were single samples.
- Optional `SPEEDLOG_SERVER_ID` pinning. Unpinned selection swung the median 307.62 → 321.04 Mbit across servers, pure measurement artifact.
- New `bin/speedlog-heartbeat`: alerts via `SPEEDLOG_ALERT_CMD` when the newest row goes stale. Telegram delivery verified.
- Hardened two latent bugs found in self-review: `grep | tail` under `pipefail` killed the heartbeat silently on a zero-byte CSV (the exact failure it exists to catch), and a null `isp`/`server.name` aborted jq under `set -e`, discarding a good measurement. Both covered by tests.
- Commas in ISP/server names are now stripped, so a name like "Test, Server" can no longer corrupt row width.
- 28 tests pass in 0.16s.

### Not done
- **Codex review skipped**: usage limit hit, resets 20 Aug 2026. Self-reviewed instead. Re-run before merging the PR.
- Cron cutover from `/Users/macmini/scripts/speedtest_monitor.sh` to `speedlog-collect` still pending: `crontab` writes are blocked from an automation shell on this Mac, needs a Full Disk Access terminal.
- `com.speedlog.dashboard` LaunchAgent still not loaded; dashboard currently running from a manual `nohup`.

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
