# Deadlock Stat Tracker

A full-stack Deadlock dashboard for searching Steam players and exploring their match performance. Built with React, Vite, FastAPI, and PostgreSQL, and deployed on AWS EC2 with Docker Compose and Caddy.

## Live Demo

**[Launch Deadlock Tracker](https://www.deadlocktracker.ca/)**

[![Animated demo showing player search and switching between Season 1 and All Matches](docs/demo.gif)](https://www.deadlocktracker.ca/)

Search for a Steam player, select a result, and switch between **Season 1** and **All Matches**. Click the preview to try the live application.

## Features

- Steam player search with names and avatars.
- **Season 1:** ranked matches within the configured Season 1 dates.
- **All Matches:** every match mode available in the player's returned history, across all dates.
- Total matches, wins, losses, win rate, K/D ratio, and average souls per match.
- Most-played heroes for the selected scope and overall history.
- PostgreSQL storage for calculated Season 1 statistics, with conditional cache reuse.
- HTTPS certificates, renewal, and domain redirects managed by Caddy.

## How Stats Are Calculated

| Metric | Calculation |
| --- | --- |
| Total Matches | Every match in the selected scope, including unknown and unscored outcomes |
| Wins / Losses | Matches with player outcome codes `1` / `2` |
| Win Rate | Wins divided by wins plus losses; unknown and unscored outcomes are excluded |
| K/D Ratio | Total kills divided by total deaths across the selected matches; total kills if there are no deaths |
| Avg Souls / Match | Average reported `net_worth` across the selected matches |
| Unscored | Outcomes other than win/loss within the last 90 days, limited to the selected scope |

Total Matches can exceed Wins + Losses + Unscored because the Unscored card uses a 90-day window. K/D and average souls include all selected matches, including those without a scored outcome.

The current Season 1 filter runs from **July 30, 2026 at 17:00 UTC**, inclusive, to **November 5, 2026 at 05:00 UTC**, exclusive. These boundaries and ranked mode (`match_mode = 4`) are configured in `main.py`.

Stats reflect the history returned by the community API. Missing or delayed upstream matches can affect totals; this dashboard does not guarantee complete or real-time Steam history.

## Project Structure

```text
.
|-- main.py                         # FastAPI routes, filtering, and calculations
|-- database.py                     # SQLAlchemy model and database initialization
|-- requirements.txt                # Python dependencies
|-- compose.yaml                    # Active production service configuration
|-- Caddyfile                       # HTTPS proxy and domain redirects
|-- Dockerfile                      # Backend image
|-- .env.example                    # Example local database connection string
|-- tests/test_summary_status.py    # Backend regression tests
|-- docs/demo.gif                   # README demo animation
`-- deadlock-dashboard/             # React + Vite frontend and Nginx image
```

## Production Deployment

Requires Docker Engine with Docker Compose. The current `compose.yaml` runs PostgreSQL 16, FastAPI, the frontend's Nginx server, and Caddy. The container builds use Python 3.12 and Node.js 22.

Create an untracked `.env` file at the repository root containing:

```dotenv
POSTGRES_PASSWORD=REPLACE_WITH_A_LONG_RANDOM_HEX_PASSWORD
```

Replace the placeholder before starting. The production configuration requires this value and supplies `DATABASE_URL` to the backend automatically. `.env.example` contains a connection string for running Python directly; it does not supply the Compose password.

For a deployment on your own domain, update the domains in `Caddyfile`, point their DNS records to the server, and allow inbound TCP ports **80** and **443**. Restrict SSH port **22** to trusted IP addresses. Keep database and backend ports private.

From the repository root:

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=100
```

The frontend is available on the server at `http://127.0.0.1:3000`; Caddy serves public domain traffic over HTTPS. The backend is bound to `127.0.0.1:8000`, with interactive API docs at `http://127.0.0.1:8000/docs` on the server. PostgreSQL has no published host port.

Caddy persists certificates in `caddy_data`, and PostgreSQL persists data in `postgres_data`. Services use `restart: unless-stopped`.

```bash
# Rebuild after application changes
docker compose up --build -d

# Inspect application logs
docker compose logs --tail=100 backend frontend caddy

# Stop the stack while retaining data
docker compose down
```

Do not add `-v` to the stop command unless you intend to delete the persistent volumes, including database data and certificates.

## Local Development

Use Python 3.12, Node.js 22.12 or newer, and a separately accessible PostgreSQL instance. The production Compose database is private to its Docker network, so Python running on your host cannot reach it through `localhost:5432` by default.

### Backend

PowerShell example, from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg2://postgres:YOUR_PASSWORD@127.0.0.1:5432/deadlock"
python -m uvicorn main:app --reload
```

Create the `deadlock` database in your local PostgreSQL instance first. The backend creates its tables on startup. Set `DATABASE_URL` in the shell before starting; the application does not load a `.env` file itself.

On Linux/macOS, activate with `source .venv/bin/activate` and set the connection string using `export DATABASE_URL='...'`.

### Frontend

In a second terminal:

```bash
cd deadlock-dashboard
npm ci
npm run dev
```

Vite is configured for **http://localhost:3000** and proxies `/api` requests to `http://127.0.0.1:8000`. If port 3000 is occupied, use the URL Vite prints or stop the service using that port.

```bash
npm run lint
npm run build
```

## API Routes

| Route | Purpose |
| --- | --- |
| `GET /` | Basic backend status response |
| `GET /api/player/search?query=<name>` | Search Steam players by name |
| `GET /api/player/{account_id}/summary?scope=season1` | Season 1 ranked statistics; default scope |
| `GET /api/player/{account_id}/summary?scope=all` | Statistics for all returned match modes and dates |

Public `/api` requests pass through Caddy and the frontend's Nginx proxy. The root status route and `/docs` are accessed directly through the backend, not the public frontend root.

## Backend Tests

With Python dependencies installed, run from the repository root:

```bash
python -m unittest discover -s tests -v
```

The tests mock upstream responses and database access. They cover inclusion of unranked matches in All Matches, exclusion from Season 1, unknown-outcome totals and win rates, and missing upstream profiles.

## Configuration and Data

Keep `.env`, private keys, credentials, and database backups out of Git. Changing `POSTGRES_PASSWORD` after PostgreSQL has initialized does not automatically change the existing database user's password.

Player search, match history, and hero information come from the community [Deadlock API](https://deadlock-api.com/). This is an independent project, not an official Valve service.
