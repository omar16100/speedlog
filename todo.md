# speedlog todo

## 2026-09-27

README accuracy and CI. Branch `fix/readme-accuracy-ci`, plan `docs/27092026_readme_accuracy_ci_plan.md`.

- README tagline and features rewritten to match the code: two bash scripts (`speedlog-collect`, `speedlog-heartbeat`) plus a FastAPI/uvicorn dashboard, not "one bash script, one HTML file". Dropped "simplest", "real-time" (page polls every 5 min) and "zero-config".
- README config table now lists all env vars read by the scripts and `app.py`; added a note that the dashboard has no auth, so binding to `0.0.0.0` exposes `POST /api/run-test`.
- Quick Start install steps now match `install.sh` order; noted that it does not install `speedlog-heartbeat` (also in `docs/index.md`).
- Em dashes removed from README, `docs/index.md` overview, `install.sh` and this file; `install.sh` usage comment pointed at the wrong GitHub owner, fixed.
- Added `.github/workflows/ci.yml`: checkout v7, setup-uv v10.2.0, Python 3.12, `uv run pytest -v`. No ruff (not configured). `uv.lock` stays gitignored, so CI resolves fresh.
- Machine-specific absolute paths in this file replaced with `~`.
- Codex (gpt-6-astra) review: no blocker/major; 4 minors applied (retry wording, failure classes not attributed to Ookla, installer env vars + hardcoded timeouts documented, `brew install speedtest` needs Ookla's tap: `teamookla/speedtest/speedtest`, also fixed in `docs/index.md` and the `install.sh` hint).
- 34 tests pass locally with the CI command.

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

### Kimi review round (18 Aug 2026)

Adversarial review by kimi found 13 issues; 10 fixed, 3 accepted as-is.

- **Silent loss of a completed measurement.** jq was unguarded, so malformed JSON or a null `.ping.latency` (jq raises on `null * 100`) killed the run under `set -e` with no CSV row and no error-log entry. The same failure class this PR exists to remove, moved one stage down the pipe. Now recorded as `parse_error` with the raw result preserved.
- **The new metric re-created the original bug.** `TOOL_ERROR_STATUSES` included `"unknown"`, so all 389 legacy failures were counted as confirmed tool errors: asserting a cause that was never recorded. Split into `tool_error_count` (0) and `unclassified_error_count` (389). This also forced a correction to the blog draft's central claim.
- **`_parse_row` crashed the whole API on one bad row.** Any non-numeric, non-`ERROR` value raised `ValueError`, 500-ing `/api/data` entirely. Now treated as a failed row.
- **`RUN_TEST_TIMEOUT_SECONDS = 120` was shorter than the collector's retry worst case**, so the API path could never complete a retry and SIGKILLed mid-measurement, leaking the temp file. Raised to 300 with the arithmetic documented.
- **No mutual exclusion between cron and `POST /api/run-test`.** Two concurrent speed tests saturate the line against each other and both rows land marked `ok` carrying meaningless numbers. Added a mkdir-based lock (macOS has no `flock(1)`) with 30-minute stale reaping.
- **Malformed `SPEEDLOG_STALE_HOURS` killed the heartbeat before `alert()` was reachable**, i.e. the alarm failed silently, the precise failure it exists to catch. Validated up front.
- **False "delivery failed" via SIGPIPE** when an alert sender exits without draining stdin. Switched the pipe to a here-string.
- Also: numeric validation of `SPEEDLOG_SERVER_ID` (a comma would widen the row), a header-mismatch warning, and `printf` instead of `echo` when feeding jq.

Rejected one suggested fix: defaulting missing measurements to `0` via `// 0`. A fabricated 0 ms ping is indistinguishable from a real one once written and would drag every average that reads the column. Failing loudly as `parse_error` is correct.

Accepted without change: the `409` TOCTOU in `run-test` (harmless, semantics are "queued"), the timestamp being measurement-start, and the collector's bash logic having no test coverage.

34 tests pass.

### Not done
- **Codex review skipped**: usage limit hit, resets 20 Aug 2026. Kimi reviewed instead and found 4 high-severity defects that self-review had missed. Codex still worth running when credits return.
- Cron cutover DONE by a different route: `crontab` writes are blocked from an automation shell (the cron spool needs Full Disk Access, and `TMPDIR=/tmp` does not help), so `~/scripts/speedtest_monitor.sh` was rewritten as a thin wrapper that `exec`s `speedlog-collect`. The untouched `0 * * * *` line now runs the new code, sleeping 420s to land at `:07`.
- `com.speedlog.dashboard` LaunchAgent still not loaded; dashboard currently running from a manual `nohup`.

## 2026-04-11
- Added `POST /api/run-test` endpoint in `src/speedlog/app.py`: subprocesses `bin/speedlog-collect`, asyncio lock, 120s timeout, returns parsed last CSV row.
- Added `RUN TEST` button in `src/speedlog/static/index.html` header (HTML + CSS + JS handler). Calls `/api/run-test`, refreshes dashboard on success, handles 409 (in-progress) and failures.
- Added 5 pytest tests in `tests/test_app.py`: success, failure, timeout, concurrent-409, script-not-found. All 18 tests pass.
- Switched live launchd service from `~/projects/speedtest-dashboard/app.py` to canonical speedlog package via `~/Library/LaunchAgents/com.speedlog.dashboard.plist`. New env: `SPEEDLOG_DATA_DIR=~/logs`, `SPEEDLOG_HOST=0.0.0.0`, `SPEEDLOG_PORT=8050`, `SPEEDLOG_ROOT_PATH=/speedtest`, `SPEEDTEST_BIN=/opt/homebrew/bin/speedtest`, PATH includes `/opt/homebrew/bin` for jq.
- Symlinked `bin/speedlog-collect` into `.venv/bin/` so `shutil.which` finds it.
- End-to-end verified: real speedtest ran via `curl -X POST http://127.0.0.1:8050/api/run-test`, row landed in `~/logs/speedtest_log.csv`.

## Backlog
- `pyproject.toml` does not ship `bin/speedlog-collect` as a console script. The symlink workaround works for editable installs but breaks for `pip install speedlog` from PyPI. Either bundle as data file + entry point, or document install.sh as the only supported install path.
- Old `~/projects/speedtest-dashboard/` fork is now unused and can be deleted after a few days of stable speedlog operation.
- `_run_test_lock` only protects in-process; cron collector at `~/scripts/speedtest_monitor.sh` could collide on simultaneous CSV writes. Low risk; mitigate with file lock if it surfaces.
- Found during the 27 Sep 2026 README pass, not fixed (out of scope):
  - `contrib/speedlog-dashboard.service` uses `WorkingDirectory=%h/speedlog`, but `install.sh` clones to `~/.local/share/speedlog/repo`.
  - `docs/c4model.md` has no component for `POST /api/run-test`.
  - `index.html` writes server names into `innerHTML` unescaped.
  - Starlette warns that using `httpx` with `TestClient` is deprecated (`httpx2`).
  - Stats in `docs/index.md` (136-day sample, 12.5%, 39.2%, 389, 2,719 samples, 307.62/321.04 Mbit, 175 hours, six weeks) come from the owner's own CSV, which is not in the repo.
