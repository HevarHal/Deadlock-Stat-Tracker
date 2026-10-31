# Deadlock Stat Tracker

A Deadlock player dashboard with hero-based themes, high-resolution artwork, ranked statistics, and paginated match history. Built with FastAPI, PostgreSQL, and a lightweight JavaScript frontend powered by Vite.

**Live site:** [deadlocktracker.ca](https://deadlocktracker.ca)

## Demo

![Player lookup, All Matches statistics, and Season 1 ranked statistics](docs/demo.gif)

The demo uses a public account and shows the deployed dashboard. Statistics change as new matches become available.

[View the full dashboard screenshot](docs/dashboard.png).

## Features

- Search Steam players by name or account ID, with avatars in name-search results.
- Switch between All Matches and Season 1 ranked statistics.
- View match totals, wins, losses, win rate, kill/death ratio, average souls, and unscored matches.
- Display the most-played hero for the selected scope, with compressed WebP renders and artwork-matched themes.
- Show the highest recorded rank across available history for All Matches, or the latest reported rank within Season 1.
- Browse match history with hero portraits, per-game rank badges, outcomes, K/D/A, souls, and duration.
- Keep profile statistics visible while refreshing match history when changing scope.
- Cache Season 1 summary statistics in PostgreSQL.

Rank badges depend on upstream availability. Missing badges display as unavailable; all-time rank means the highest rank in the match history returned by the API, not a guaranteed complete career record. Win rate uses decided wins and losses, while total matches includes all outcomes.

## Run with Docker

Install Docker with Compose, then run from the repository root:

```sh
docker compose up -d --build
```

Open the dashboard at [localhost:3000](http://localhost:3000) and the backend API documentation at [localhost:8000/docs](http://localhost:8000/docs).

The local development Compose file provides a development database password. Production deployments require `POSTGRES_PASSWORD` in `.env` and may use Caddy for HTTPS. Keep the configuration appropriate to your environment; the local test Compose configuration should not replace production settings.

```sh
docker compose logs --tail=100
docker compose logs --tail=100 -f backend
docker compose down
```

The PostgreSQL named volume persists when stopping the stack. `docker compose down -v` deletes that volume and its data.

## Development

Use Python 3.12 and Node.js 22, matching the Docker images, plus a running PostgreSQL database.

### Backend (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg2://postgres:your-password@127.0.0.1:5432/deadlock"
python -m uvicorn main:app --reload
```

`DATABASE_URL` must be present in the process environment. `.env.example` documents its format; the Python application does not automatically load that file.

### Frontend

```sh
cd deadlock-dashboard
npm ci
npm run dev
```

Vite uses port 3000 and proxies `/api` to `http://127.0.0.1:8000`. Stop the Docker frontend first if it already occupies port 3000, or choose another port with `npm run dev -- --port 3001`.

```sh
npm run build
npm run lint
```

### Backend tests

From the repository root, with the Python dependencies installed:

```sh
python -m unittest discover -s tests -v
```

Tests mock upstream requests and use an in-memory database configuration.

## API

| Route | Purpose |
| --- | --- |
| `GET /` | Backend health status |
| `GET /api/player/search?query=<name>` | Steam player lookup |
| `GET /api/player/{account_id}/summary?scope=all` | Summary statistics |
| `GET /api/player/{account_id}/matches?scope=season1&page=1&page_size=20` | Paginated matches and profile rank metadata |

Supported scopes are `all` and `season1`. Match pages start at 1; page size is between 1 and 100. Interactive route documentation is available at `/docs` on the backend.

## Project structure

```text
main.py                              FastAPI routes and statistics
 database.py                         SQLAlchemy models and database setup
 tests/                              Backend regression tests
 deadlock-dashboard/
   index.html                        Dashboard markup
   src/profile-app.js                Player search and dashboard behavior
   src/hero-theme.js                 Hero palette application
   src/hero-palettes.json            Colors sampled from hero artwork
   public/dashboard.css              Layout, artwork blending, and table styles
   public/assets/                    Hero catalogs, rank metadata, and WebP renders
 docs/                               Demo animation and screenshot
```

## Data and artwork

Player data comes from the [Deadlock API](https://deadlock-api.com/). Hero renders originate from the [Deadlock Wiki](https://deadlock.wiki/) and are converted to WebP; small API card portraits are retained as fallbacks. See [artwork sources](deadlock-dashboard/public/assets/SOURCES.md).

The bundled image catalogs contain 44 released heroes as verified on October 30, 2026. Refresh the catalogs and palettes when the roster changes.

Deadlock and its game artwork belong to Valve. This is an independent community project.

## Configuration

Keep `.env`, SSH keys, credentials, dependency folders, and database dumps out of Git. Frontend production output is generated in `deadlock-dashboard/dist/`. Production Compose and Caddy settings should remain specific to the deployment.
