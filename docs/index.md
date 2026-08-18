# Speedlog Documentation

## Overview

Speedlog is a minimal internet speed monitoring tool. It consists of two components:

1. **speedlog-collect** — a bash script that runs a speed test (via Ookla CLI) and appends results to a CSV file
2. **speedlog-dashboard** — a FastAPI web server that reads the CSV and renders an interactive Chart.js dashboard

No database, no Docker, no complex setup.

## Architecture

```
[Cron / Systemd Timer]
        |
        v
[speedlog-collect]  --->  [speedtest_log.csv]  <---  [speedlog-dashboard (FastAPI)]
   (bash + jq)                (flat file)                     |
        |                                                     v
        v                                              [Browser (Chart.js)]
[Ookla Speedtest CLI]
```

See [c4model.md](c4model.md) for detailed architecture diagrams.

## Quick Start

### Prerequisites

- [Ookla Speedtest CLI](https://www.speedtest.net/apps/cli) (`brew install speedtest` on macOS)
- [jq](https://jqlang.github.io/jq/) (`brew install jq` on macOS, `apt install jq` on Linux)
- [uv](https://docs.astral.sh/uv/) (for the dashboard)

### Install (one-liner)

```bash
curl -fsSL https://raw.githubusercontent.com/omar16100/speedlog/main/install.sh | bash
```

This clones the repo to `~/.local/share/speedlog/repo`, installs `speedlog-collect` to `~/.local/bin/`, creates the data directory, and installs dashboard dependencies.

### Run a test

```bash
speedlog-collect
```

### Start the dashboard

```bash
cd ~/.local/share/speedlog/repo && uv run speedlog-dashboard
# Open http://127.0.0.1:8080
```

### Schedule hourly collection

```bash
crontab -e
# Add: 0 * * * * ~/.local/bin/speedlog-collect
```

## Configuration

All configuration is via environment variables with sensible defaults:

| Variable | Default | Description |
|---|---|---|
| `SPEEDLOG_DATA_DIR` | `$HOME/.local/share/speedlog` | Directory for CSV data and error logs |
| `SPEEDLOG_PORT` | `8080` | Dashboard HTTP listen port |
| `SPEEDLOG_HOST` | `127.0.0.1` | Dashboard bind address |
| `SPEEDLOG_ROOT_PATH` | `/` | FastAPI root_path for reverse proxy setups |
| `SPEEDTEST_BIN` | auto-detected | Override path to the Ookla speedtest binary |
| `SPEEDLOG_SERVER_ID` | unset (auto-select) | Pin a specific Ookla server id, passed as `--server-id` |
| `SPEEDLOG_RETRY_DELAY` | `60` | Seconds to wait before the single retry |
| `SPEEDLOG_STALE_HOURS` | `3` | Heartbeat alerts once the newest sample is older than this |
| `SPEEDLOG_ALERT_CMD` | unset | Command receiving the heartbeat alert on stdin |

### Why pin a server

Ookla's automatic server selection moves between endpoints, and their medians
differ. Across 2,719 samples on one line the median by server ranged from
307.62 Mbit to 321.04 Mbit. That 13 Mbit spread is measurement variance, not
line variance, and it makes a long series incomparable with itself. Pin
`SPEEDLOG_SERVER_ID` if you care about trends rather than snapshots.

## CSV Format

```csv
timestamp,ping_ms,download_mbit,upload_mbit,isp,server,status,server_id
2026-08-18 10:00:00,5.5,307.9,52.4,TM Net,Server A,ok,45610
2026-08-18 11:00:00,5.6,308.1,52.3,TM Net,Server A,ok_retry,45610
2026-08-18 12:00:00,ERROR,ERROR,ERROR,ERROR,ERROR,config_unavailable,45610
```

### The `status` column

A failing speed test often means the *tool* failed, not the connection. On one
136-day sample, 12.5% of runs recorded an error. Every error message in the
log was Ookla-side (configuration 503s, `NoServers`, connect timeouts) and
none indicated a local link failure, and errors peaked at 39.2% at 00:00 local
(16:00 UTC) against a 5-13% baseline, which no real outage would do.

That is strong evidence, but note what it is not: because the old collector
recorded no cause per row, not one of those 389 failures can be attributed
individually, even now. That is the whole argument for recording the cause at
write time rather than reconstructing it later.

Without a cause recorded, that distinction is unrecoverable after the fact.
`status` records it at write time:

| Status | Meaning |
|---|---|
| `ok` | Test succeeded on the first attempt |
| `ok_retry` | First attempt failed, the retry succeeded |
| `config_unavailable` | Ookla's configuration endpoint refused (503 etc) |
| `no_servers` | Ookla found no working test server |
| `connect_timeout` | Connection to the test server timed out |
| `parse_error` | The test completed but its output could not be parsed. The raw result is written to the error log. |
| `unknown` | Failure that matched no known class, or a legacy row predating this column |

Only `ok` and `ok_retry` are successes. Everything else is a failed
measurement, and none of them is direct evidence about your connection.

`unknown` is reported separately from the classified failures, and is
deliberately **not** counted as a tool error. Rows written before this column
existed all parse as `unknown`, and counting them as tool failures would
assert a cause that was never recorded, which is the same misattribution the
column exists to prevent. The API exposes `tool_error_count` (positively
identified) and `unclassified_error_count` (cause unknown) separately.

### Concurrency

Only one measurement runs at a time. The collector takes an exclusive lock
(`$SPEEDLOG_DATA_DIR/.collect.lock`, mkdir-based since macOS has no
`flock(1)`) and exits rather than queueing if another run holds it. Two speed
tests running together saturate the link against each other, and both rows
would be written marked `ok` while carrying meaningless bandwidth. A lock
older than 30 minutes is treated as stale and reaped.

### Legacy formats

4-column (pre-ISP), 6-column (pre-status) and 8-column rows all parse. Legacy
successes report `status=ok`; legacy failures report `unknown` rather than a
cause that was never recorded.

## Heartbeat

A monitor that only alerts on bad numbers cannot alert on *no* numbers. In the
same 136-day sample, 175 consecutive hours went missing without anyone
noticing, and the dashboard itself sat dead for six weeks.

```bash
speedlog-heartbeat   # exit 0 if fresh, exit 1 and alert if stale
```

Schedule it separately from the collector, so a wedged collector cannot
silence its own alarm:

```bash
23 */3 * * * SPEEDLOG_ALERT_CMD="..." ~/.local/bin/speedlog-heartbeat
```

`SPEEDLOG_ALERT_CMD` receives the message on stdin. Anything that reads stdin
works, for example a Telegram or ntfy sender. Leave it unset to report to
stderr only, which cron will mail.

## Reverse Proxy

### Nginx

```nginx
location /speedtest/ {
    proxy_pass http://127.0.0.1:8080/;
}
```

Set `SPEEDLOG_ROOT_PATH=/speedtest` when starting the dashboard.

### Caddy

```
reverse_proxy /speedtest/* 127.0.0.1:8080
```

### Tailscale Serve

```bash
tailscale serve --bg --set-path /speedtest http://127.0.0.1:8080
SPEEDLOG_ROOT_PATH=/speedtest uv run speedlog-dashboard
```

## Systemd Setup (Linux)

```bash
# Copy unit files
mkdir -p ~/.config/systemd/user
cp contrib/speedlog-collect.service ~/.config/systemd/user/
cp contrib/speedlog.timer ~/.config/systemd/user/
cp contrib/speedlog-dashboard.service ~/.config/systemd/user/

# Enable and start
systemctl --user enable --now speedlog.timer
systemctl --user enable --now speedlog-dashboard

# Check status
systemctl --user status speedlog.timer
systemctl --user status speedlog-dashboard
journalctl --user -u speedlog-collect -f
```

## Migrating Existing Data

If you have an existing `speedtest_log.csv`, copy it to the data directory:

```bash
cp /path/to/old/speedtest_log.csv ~/.local/share/speedlog/speedtest_log.csv
```

The dashboard handles 4-column (original), 6-column (with ISP and server) and 8-column (with status and server id) formats automatically, including a file that mixes all three.

If your existing header does not match the current 8-column schema, the collector warns rather than rewriting it: the header is your data, not the tool's. Fix it by hand when convenient.
