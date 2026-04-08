# Speedlog C4 Architecture

## Level 1: System Context

```mermaid
C4Context
    title Speedlog System Context

    Person(user, "User", "Views speed test history via browser")
    System(speedlog, "Speedlog", "Monitors and visualizes internet speed over time")
    System_Ext(ookla, "Ookla Speedtest", "Speed test infrastructure")

    Rel(user, speedlog, "Views dashboard")
    Rel(speedlog, ookla, "Runs speed tests against")
```

The user schedules periodic speed tests. Results are stored locally and visualized through a web dashboard.

## Level 2: Container

```mermaid
C4Container
    title Speedlog Containers

    Person(user, "User")

    Container_Boundary(speedlog, "Speedlog") {
        Container(collect, "speedlog-collect", "Bash + jq", "Runs Ookla speedtest, parses JSON, appends CSV")
        ContainerDb(csv, "speedtest_log.csv", "CSV File", "Stores all test results as flat-file rows")
        Container(dashboard, "speedlog-dashboard", "Python / FastAPI", "Serves API and static dashboard HTML")
        Container(browser, "Dashboard UI", "HTML + Chart.js", "Renders charts and stats in the browser")
    }

    System_Ext(ookla, "Ookla Speedtest Servers")
    System_Ext(cron, "Cron / Systemd Timer")

    Rel(cron, collect, "Triggers hourly")
    Rel(collect, ookla, "Runs speed test")
    Rel(collect, csv, "Appends results")
    Rel(dashboard, csv, "Reads data")
    Rel(user, browser, "Views")
    Rel(browser, dashboard, "Fetches /api/data")
```

## Level 3: Component (Dashboard)

```mermaid
C4Component
    title speedlog-dashboard Components

    Container_Boundary(dashboard, "speedlog-dashboard") {
        Component(index_route, "GET /", "FastAPI route", "Serves static index.html")
        Component(api_route, "GET /api/data", "FastAPI route", "Reads CSV, computes stats, returns JSON")
        Component(parse_row, "_parse_row()", "Python function", "Parses CSV rows, handles 4-col and 6-col formats")
        Component(csv_path, "_csv_path()", "Python function", "Resolves data dir from SPEEDLOG_DATA_DIR env var")
        Component(static, "static/index.html", "HTML + JS", "Chart.js dashboard with auto-refresh")
    }

    ContainerDb(csv, "speedtest_log.csv")

    Rel(index_route, static, "Serves")
    Rel(api_route, csv_path, "Calls")
    Rel(api_route, parse_row, "Calls per row")
    Rel(csv_path, csv, "Resolves path to")
```

## Data Flow

1. **Collection**: Cron triggers `speedlog-collect` → runs `speedtest --format=json` → pipes through `jq` → appends row to CSV
2. **Dashboard**: Browser loads `/` → fetches `/api/data` → FastAPI reads CSV, computes stats (avg/min/max/latest, error rate, server distribution) → returns JSON → Chart.js renders
3. **Refresh**: Dashboard auto-refreshes every 5 minutes via `setInterval`
