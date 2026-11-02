# Deadlock Stat Tracker

A Deadlock player dashboard with hero-based themes, high-resolution artwork, ranked statistics, and paginated match history. Built with FastAPI, PostgreSQL, and a lightweight JavaScript frontend powered by Vite.

**Live site:** [deadlocktracker.ca](https://deadlocktracker.ca)

## Demo

![Player lookup, All Matches statistics, and Season 1 ranked statistics](docs/demo.gif)

The demo uses a public account and shows the deployed dashboard. Statistics change as new matches become available.

## Features

- Search Steam players by name or account ID, with avatars in name-search results.
- Switch between All Matches and Season 1 ranked statistics.
- View match totals, wins, losses, win rate, kill/death ratio, average souls, and unscored matches.
- Display the most-played hero for the selected scope, with compressed WebP renders and artwork-matched themes.
- Show the highest recorded rank across available history for All Matches, or the latest reported rank within Season 1.
- Browse match history with hero portraits, per-game rank badges, outcomes, K/D/A, souls, and duration.
- Expand a match to view a centered, wrapping item timeline grouped into five-minute intervals, using in-game shop icons.
- Show actual item sales as crossed-out icons at the time of sale; components consumed by upgrades are not reported as sold.
- View the starting build guide's name, build ID, and description when available.
- Copy build and match IDs with one click; the confirmation clears after one second.
- Remember the selected player, scope, history page, search text, and scroll position for the current tab. Refresh reloads the same view.
- Keep profile statistics visible while refreshing match history when changing scope.
- Cache Season 1 summary statistics in PostgreSQL.

Rank badges depend on upstream availability. Missing badges display as unavailable; all-time rank means the highest rank in the match history returned by the API, not a guaranteed complete career record. Win rate uses decided wins and losses, while total matches includes all outcomes.

Item timelines and starting guides depend on available match metadata and processed replay data. The recorded guide is the one selected at match start; later guide switches are not recorded, and the available guide may have changed since the match. Missing data is shown as unavailable, with retry controls for failed requests.

Tab memory uses browser `sessionStorage`, rather than permanently saving the view. A new independent tab starts fresh; browser tab-restoration features may restore saved state. Refreshing reloads player data through the existing API routes; it does not add a new database cache policy.

## Run with Docker

Install Docker with Compose, then run from the repository root:

```sh
docker compose up -d --build
```

Open the dashboard at [localhost:3000](http://localhost:3000) and the backend API documentation at [localhost:8000/docs](http://localhost:8000/docs).

Compose requires `POSTGRES_PASSWORD` in `.env`. The frontend and backend ports bind to localhost, while Caddy provides public HTTP/HTTPS access. Adjust the Caddy hostname and production settings for your environment; do not replace a running deployment's environment or database volumes when updating application code.

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
npm test
```

Frontend tests cover purchase/sale timeline grouping, tab-state validation, and shared number/time formatting.

### Backend tests

From the repository root, with the Python dependencies installed:

```sh
python -m unittest discover -s tests -v
```

Tests mock upstream requests and database access. They cover search ordering, statistics, scope filtering, pagination, rank badges, item purchases versus upgrade consumption, and missing guide or match data.

## API

| Route | Purpose |
| --- | --- |
| `GET /` | Backend health status |
| `GET /api/player/search?query=<name>` | Steam player lookup |
| `GET /api/player/{account_id}/summary?scope=all` | Summary statistics |
| `GET /api/player/{account_id}/matches?scope=season1&page=1&page_size=20` | Paginated matches and profile rank metadata |
| `GET /api/player/{account_id}/matches/{match_id}/build` | Item purchase timeline and available starting build guide |

Supported scopes are `all` and `season1`. Match pages start at 1; page size is between 1 and 100. Interactive route documentation is available at `/docs` on the backend.

## Project structure

```text
main.py                              Player search, match history, and summary routes
database.py                          SQLAlchemy models and database setup
match_details.py                     Item timelines and starting build-guide route
tests/                               Backend regression tests
deadlock-dashboard/
  index.html                         Dashboard markup
  src/profile-app.js                 Player search, loading, and page coordination
  src/match-table.js                 Match rows, portraits, and rank rendering
  src/match-build.js                 Expandable timelines and ID copy controls
  src/tab-state.js                   Per-tab view persistence
  src/format.js                      Shared number and time formatting
  src/hero-theme.js                  Hero palette application
  src/hero-palettes.json             Colors sampled from hero artwork
  tests/                             Frontend regression tests
  public/dashboard.css              Layout, responsive styles, and match panels
  public/assets/                    Hero catalogs, rank metadata, and WebP renders
docs/                                Demo animation and screenshot
```

## Data and artwork

Player data comes from the [Deadlock API](https://deadlock-api.com/). Hero renders originate from the [Deadlock Wiki](https://deadlock.wiki/) and are converted to WebP; small API card portraits are retained as fallbacks. See [artwork sources](deadlock-dashboard/public/assets/SOURCES.md).

The bundled image catalogs contain 44 released heroes as verified on October 30, 2026. Refresh the catalogs and palettes when the roster changes.

Deadlock and its game artwork belong to Valve. This is an independent community project.

## Configuration

Keep `.env`, SSH keys, credentials, dependency folders, and database dumps out of Git. Frontend production output is generated in `deadlock-dashboard/dist/`. Production Compose and Caddy settings should remain specific to the deployment.
