# README accuracy and CI plan (27 Sep 2026)

## Status

Done on branch `fix/readme-accuracy-ci`, pending review and merge.

## Goal

Make the README describe what the repo actually ships, and add CI so the test
suite runs on every push to `main` and every pull request.

## Problems found

- README tagline and GitHub description said "One bash script, one HTML file".
  The repo ships two bash scripts (`bin/speedlog-collect`,
  `bin/speedlog-heartbeat`), an installer, and a FastAPI/uvicorn app
  (`src/speedlog/app.py`) that serves `src/speedlog/static/index.html`.
- "The simplest internet speed monitor" is an unbacked superlative.
- "real-time dashboard": the page polls `/api/data` every 5 minutes
  (`setInterval` in `index.html`), it does not stream.
- "Zero-config defaults, works out of the box": reworded to what the code does
  (every setting has a default in the scripts or `app.py`).
- Configuration table omitted `SPEEDLOG_SERVER_ID`, `SPEEDLOG_RETRY_DELAY`,
  `SPEEDLOG_STALE_HOURS`, `SPEEDLOG_ALERT_CMD`.
- README did not mention the Run Test button (`POST /api/run-test`) or
  `speedlog-heartbeat`, and did not say the dashboard has no authentication.
- Quick Start described the installer steps in the wrong order and omitted
  the `uv sync` step. `install.sh` does not install `speedlog-heartbeat`.
- Em dashes (U+2014) in README and `docs/index.md` prose.
- No CI.

## Changes

- `README.md`: rewritten tagline and features; installer steps match
  `install.sh`; full env var table; security note on binding to `0.0.0.0`;
  no em dashes.
- `docs/index.md`: em dashes removed from the overview, note that
  `install.sh` does not copy `speedlog-heartbeat`, link to this plan.
- `.github/workflows/ci.yml`: checkout, setup-uv, `uv run pytest -v` on
  Python 3.12 (the `requires-python` floor).
- `install.sh`: usage comment pointed at the wrong GitHub owner
  (`omarshabab`), fixed; brew hint corrected; em dashes removed from a comment
  and an echo string.
  No behaviour change.
- `todo.md`: dated entry; machine-specific absolute paths replaced with `~`;
  out-of-scope findings added to the backlog.

## Decisions

- `uv.lock` stays gitignored (existing repo choice). CI resolves the newest
  versions allowed by `pyproject.toml`, so it also catches upstream breakage.
- No ruff step: ruff is not configured in `pyproject.toml`.
- Tests never touch the network: `/api/run-test` tests monkeypatch
  `subprocess.run` and `_resolve_collect_script`.
- `astral-sh/setup-uv` no longer publishes a floating major tag after v7, so
  the workflow pins the full `v10.2.0` tag.

## Review

Codex (gpt-6-astra), output in the sweep's codex folder: no blocker or major.
Four minors, all applied:

- Retry wording: only a CLI failure triggers the retry; a parse failure does not.
- "Ookla-side errors" overstated attribution; the classes are matched from
  the CLI's error text, so the README now says that.
- "Every setting has a default" was too broad: the run-test timeout and the
  refresh interval are hardcoded, and `install.sh` reads `INSTALL_DIR` and
  `SPEEDLOG_REPO_DIR`. Both now documented.
- `brew install speedtest` fails without Ookla's tap (homebrew-core only has
  the unrelated `speedtest-cli`). Now `brew install
  teamookla/speedtest/speedtest` in README, `docs/index.md` and the
  `install.sh` hint.

## Deviations

- `install.sh` touched (comment, two hint strings) although the task was
  README-focused: the usage URL and the brew hint were wrong.
