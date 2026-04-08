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

## CSV Format

```csv
timestamp,ping_ms,download_mbit,upload_mbit,isp,server
2026-04-07 10:00:00,5.0,300.0,50.0,TM Net,Server A
2026-04-07 11:00:00,ERROR,ERROR,ERROR,ERROR,ERROR
```

Failed tests are logged as ERROR rows. The dashboard handles both gracefully.

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

The dashboard handles both 4-column (old) and 6-column (new, with ISP and server) formats automatically.
