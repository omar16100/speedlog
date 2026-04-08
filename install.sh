#!/usr/bin/env bash
set -euo pipefail

# speedlog installer — clone, check deps, set up everything
# Usage: curl -fsSL https://raw.githubusercontent.com/omarshabab/speedlog/main/install.sh | bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

SPEEDLOG_DATA_DIR="${SPEEDLOG_DATA_DIR:-$HOME/.local/share/speedlog}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"
REPO_DIR="${SPEEDLOG_REPO_DIR:-$HOME/.local/share/speedlog/repo}"
REPO_URL="https://github.com/omarshabab/speedlog.git"

echo "================================"
echo "  speedlog installer"
echo "================================"
echo ""

# --- Check dependencies ---

MISSING=0

echo "Checking dependencies..."
echo ""

# git
if command -v git &>/dev/null; then
    echo -e "  ${GREEN}[ok]${NC} git"
else
    echo -e "  ${RED}[missing]${NC} git"
    MISSING=1
fi

# jq
if command -v jq &>/dev/null; then
    echo -e "  ${GREEN}[ok]${NC} jq $(jq --version 2>/dev/null || echo '')"
else
    echo -e "  ${RED}[missing]${NC} jq"
    echo "       Install: brew install jq (macOS) / apt install jq (Linux)"
    MISSING=1
fi

# Ookla speedtest CLI
if command -v speedtest &>/dev/null; then
    if speedtest --version 2>/dev/null | grep -qi "ookla"; then
        echo -e "  ${GREEN}[ok]${NC} speedtest (Ookla CLI)"
    else
        echo -e "  ${RED}[wrong]${NC} speedtest found but it's not the Ookla CLI"
        echo "       Install the official CLI from https://www.speedtest.net/apps/cli"
        MISSING=1
    fi
else
    echo -e "  ${RED}[missing]${NC} speedtest"
    echo "       Install from https://www.speedtest.net/apps/cli"
    echo "       macOS: brew install speedtest"
    MISSING=1
fi

# uv (for dashboard)
if command -v uv &>/dev/null; then
    echo -e "  ${GREEN}[ok]${NC} uv $(uv --version 2>/dev/null | head -1)"
else
    echo -e "  ${YELLOW}[optional]${NC} uv (needed for dashboard)"
    echo "       Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

echo ""

if [[ "$MISSING" -eq 1 ]]; then
    echo -e "${RED}Missing required dependencies. Install them and re-run.${NC}"
    exit 1
fi

# --- Clone or update repo ---

if [[ -d "$REPO_DIR/.git" ]]; then
    echo "Updating speedlog repo at $REPO_DIR..."
    git -C "$REPO_DIR" pull --quiet 2>/dev/null || true
else
    echo "Cloning speedlog to $REPO_DIR..."
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone --quiet "$REPO_URL" "$REPO_DIR"
fi
echo -e "  ${GREEN}[ok]${NC} $REPO_DIR"
echo ""

# --- Create data directory ---

echo "Setting up data directory: $SPEEDLOG_DATA_DIR"
mkdir -p "$SPEEDLOG_DATA_DIR"
echo -e "  ${GREEN}[ok]${NC} $SPEEDLOG_DATA_DIR"
echo ""

# --- Install collection script ---

COLLECT_SRC="$REPO_DIR/bin/speedlog-collect"

if [[ -f "$COLLECT_SRC" ]]; then
    mkdir -p "$INSTALL_DIR"
    cp "$COLLECT_SRC" "$INSTALL_DIR/speedlog-collect"
    chmod +x "$INSTALL_DIR/speedlog-collect"
    echo -e "Installed speedlog-collect to ${GREEN}$INSTALL_DIR/speedlog-collect${NC}"
else
    echo -e "${RED}bin/speedlog-collect not found in repo${NC}"
    exit 1
fi

# --- Install dashboard deps ---

if command -v uv &>/dev/null; then
    echo "Installing dashboard dependencies..."
    (cd "$REPO_DIR" && uv sync --quiet 2>/dev/null) && \
        echo -e "  ${GREEN}[ok]${NC} dashboard dependencies installed" || \
        echo -e "  ${YELLOW}[skip]${NC} uv sync failed — run manually: cd $REPO_DIR && uv sync"
fi

echo ""

# --- Ensure ~/.local/bin is in PATH ---

if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo -e "${YELLOW}Note:${NC} $INSTALL_DIR is not in your PATH."
    echo "  Add to your shell profile:"
    echo "    export PATH=\"$INSTALL_DIR:\$PATH\""
    echo ""
fi

# --- Next steps ---

echo "================================"
echo "  Setup complete!"
echo "================================"
echo ""
echo "  1. Set up scheduled collection:"
echo ""
echo "     crontab -e"
echo "     0 * * * * $INSTALL_DIR/speedlog-collect"
echo ""
echo "  2. Run a test:"
echo "     speedlog-collect"
echo ""
echo "  3. Start the dashboard:"
echo "     cd $REPO_DIR && uv run speedlog-dashboard"
echo ""
