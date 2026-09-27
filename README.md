# speedlog

Self-hosted internet speed monitor. A bash script runs the [Ookla Speedtest CLI](https://www.speedtest.net/apps/cli) and appends each result to a CSV file; a FastAPI app serves a Chart.js dashboard that reads that file. No database, no Docker.

## Features

- `speedlog-collect` (bash + jq): runs one measurement per invocation and appends a row to the CSV. Schedule it with cron or the systemd timer in `contrib/`.
- If the Ookla CLI exits with an error, the collector waits `SPEEDLOG_RETRY_DELAY` seconds and tries once more. Each row carries a `status` column: `ok`, `ok_retry`, a failure class matched from the CLI's error text (`config_unavailable`, `no_servers`, `connect_timeout`), `parse_error` when the result could not be parsed, or `unknown`.
- Flat-file CSV storage, no database.
- `speedlog-dashboard` (FastAPI + uvicorn): download/upload and ping charts over time, server distribution, reliability (share of successful tests), and the 20 most recent results. The page reloads its data every 5 minutes.
- Run Test button on the dashboard triggers `speedlog-collect` on demand (`POST /api/run-test`).
- `speedlog-heartbeat` (bash): alerts when the newest CSV row is older than `SPEEDLOG_STALE_HOURS`.
- Every environment variable in the tables below has a default.
- macOS and Linux: cron on either, systemd user units in `contrib/` for Linux.

## Prerequisites

- [Ookla Speedtest CLI](https://www.speedtest.net/apps/cli): `brew install teamookla/speedtest/speedtest` (macOS, Ookla's Homebrew tap) or [see install guide](https://www.speedtest.net/apps/cli). The `speedtest-cli` Python package is a different tool and is rejected by the collector.
- [jq](https://jqlang.github.io/jq/): `brew install jq` (macOS) / `apt install jq` (Linux)
- [uv](https://docs.astral.sh/uv/), for running the dashboard (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Python 3.12 or newer for the dashboard (uv can install it)

The dashboard page loads Chart.js from the jsDelivr CDN and fonts from Google Fonts, so the browser viewing it needs internet access.

## Quick Start

```bash
# One-liner install
curl -fsSL https://raw.githubusercontent.com/omar16100/speedlog/main/install.sh | bash
```

This checks dependencies, clones (or updates) the repo in `~/.local/share/speedlog/repo`, creates the data directory, copies `speedlog-collect` to `~/.local/bin/`, and runs `uv sync` for the dashboard if uv is installed. It does not install `speedlog-heartbeat`; copy it from the repo's `bin/` if you want it.

Then:

```bash
# Run a test
speedlog-collect

# Set up hourly cron
crontab -e
# Add: 0 * * * * ~/.local/bin/speedlog-collect

# Start the dashboard
cd ~/.local/share/speedlog/repo && uv run speedlog-dashboard
# Open http://127.0.0.1:8080
```

## Schedule Collection

### Cron (macOS + Linux)

```bash
crontab -e
# Add this line to run every hour:
0 * * * * ~/.local/bin/speedlog-collect
```

### Systemd Timer (Linux)

```bash
mkdir -p ~/.config/systemd/user
cp contrib/speedlog-collect.service contrib/speedlog.timer ~/.config/systemd/user/
systemctl --user enable --now speedlog.timer
```

## Configuration

Runtime settings are environment variables:

| Variable | Default | Used by | Description |
|---|---|---|---|
| `SPEEDLOG_DATA_DIR` | `~/.local/share/speedlog` | all | CSV + error log storage |
| `SPEEDLOG_PORT` | `8080` | dashboard | Dashboard listen port |
| `SPEEDLOG_HOST` | `127.0.0.1` | dashboard | Dashboard bind address |
| `SPEEDLOG_ROOT_PATH` | `/` | dashboard | Root path for reverse proxy |
| `SPEEDTEST_BIN` | auto-detected | collector | Path to Ookla speedtest binary |
| `SPEEDLOG_SERVER_ID` | unset (Ookla picks) | collector | Pin an Ookla server id (numeric) |
| `SPEEDLOG_RETRY_DELAY` | `60` | collector | Seconds to wait before the single retry |
| `SPEEDLOG_STALE_HOURS` | `3` | heartbeat | Alert once the newest row is older than this |
| `SPEEDLOG_ALERT_CMD` | unset | heartbeat | Command that receives the alert text on stdin |

Example:

```bash
SPEEDLOG_PORT=9090 SPEEDLOG_HOST=0.0.0.0 uv run speedlog-dashboard
```

The dashboard has no authentication. Binding to `0.0.0.0` exposes it to your network, including `POST /api/run-test`, which starts a speed test.

`install.sh` also reads:

| Variable | Default | Description |
|---|---|---|
| `INSTALL_DIR` | `~/.local/bin` | Where `speedlog-collect` is copied |
| `SPEEDLOG_REPO_DIR` | `~/.local/share/speedlog/repo` | Where the repo is cloned |

The `/api/run-test` timeout (300 s) and the dashboard refresh interval (5 min) are fixed in code.

## Reverse Proxy

Behind nginx, caddy, or Tailscale Serve:

```bash
# Set root path to match your proxy prefix
SPEEDLOG_ROOT_PATH=/speedtest uv run speedlog-dashboard

# Tailscale example
tailscale serve --bg --set-path /speedtest http://127.0.0.1:8080
```

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest -v

# Run dashboard locally
SPEEDLOG_DATA_DIR=./data uv run speedlog-dashboard
```

CI (`.github/workflows/ci.yml`) runs `uv run pytest -v` on every push to `main` and every pull request. The tests do not run real speed tests or touch the network.

## Documentation

- [docs/index.md](docs/index.md): full setup guide, CSV format and `status` values, heartbeat, systemd setup, migration, reverse proxy config
- [docs/c4model.md](docs/c4model.md): architecture diagrams

## License

MIT
