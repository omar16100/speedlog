# speedlog

The simplest internet speed monitor. One bash script, one HTML file, no Docker, no database.

Runs periodic speed tests via the [Ookla Speedtest CLI](https://www.speedtest.net/apps/cli), logs results to a CSV file, and serves a real-time dashboard.

## Features

- Lightweight collection script (bash + jq) — runs via cron or systemd timer
- Flat-file CSV storage — no database needed
- Interactive web dashboard with Chart.js — download/upload speed, ping, reliability, server distribution
- Zero-config defaults — works out of the box
- Handles both macOS and Linux

## Prerequisites

- [Ookla Speedtest CLI](https://www.speedtest.net/apps/cli) — `brew install speedtest` (macOS) or [see install guide](https://www.speedtest.net/apps/cli)
- [jq](https://jqlang.github.io/jq/) — `brew install jq` (macOS) / `apt install jq` (Linux)
- [uv](https://docs.astral.sh/uv/) — for running the dashboard (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Quick Start

```bash
# One-liner install
curl -fsSL https://raw.githubusercontent.com/omar16100/speedlog/main/install.sh | bash
```

This clones the repo, checks dependencies, installs `speedlog-collect` to `~/.local/bin/`, and sets up the data directory.

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

All config via environment variables:

| Variable | Default | Description |
|---|---|---|
| `SPEEDLOG_DATA_DIR` | `~/.local/share/speedlog` | CSV + error log storage |
| `SPEEDLOG_PORT` | `8080` | Dashboard listen port |
| `SPEEDLOG_HOST` | `127.0.0.1` | Dashboard bind address |
| `SPEEDLOG_ROOT_PATH` | `/` | Root path for reverse proxy |
| `SPEEDTEST_BIN` | auto-detected | Path to Ookla speedtest binary |

Example:

```bash
SPEEDLOG_PORT=9090 SPEEDLOG_HOST=0.0.0.0 uv run speedlog-dashboard
```

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

## Documentation

- [docs/index.md](docs/index.md) — full setup guide, systemd setup, migration, reverse proxy config
- [docs/c4model.md](docs/c4model.md) — architecture diagrams

## License

MIT
