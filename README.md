# Deadlock Stat Tracker

Deadlock Stat Tracker is a full-stack dashboard for searching Steam players and viewing their ranked Deadlock performance. The backend fetches match history from the Deadlock API, calculates player metrics, and caches results in PostgreSQL. The frontend is a React and Vite dashboard.

## Live Demo

**[Launch Deadlock Tracker](https://deadlocktracker.ca/)**

Search for **Spiralwind**, select the player, and switch between **Season 1** ranked stats and **All Matches** to explore the dashboard.

If the new domain does not resolve yet, use the [temporary demo address](http://3.138.109.149/).

## Features

- Search for Deadlock players by Steam name
## Features

- Search for Deadlock players by Steam name
- View ranked match totals, wins, losses, win rate, K/D ratio, and average souls
- Show most-played heroes for the selected player
- Cache calculated statistics in PostgreSQL
- React dashboard with a Vite development workflow

## Project Structure

```text
.
|-- main.py                 # FastAPI application and API routes
|-- database.py             # SQLAlchemy models and PostgreSQL setup
|-- .env.example            # Local environment configuration template
`-- deadlock-dashboard/     # React + Vite frontend
```

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- PostgreSQL, running locally or through Docker

## Backend Setup

Create and activate a virtual environment, then install the Python dependencies:

```powershell
python -m venv .venv
python -m pip install fastapi uvicorn httpx pandas sqlalchemy psycopg2-binary
```

Copy `.env.example` to `.env` and set the PostgreSQL connection string. PowerShell example:

```powershell
Copy-Item .env.example .env
$env:DATABASE_URL = "postgresql://postgres:your-password@127.0.0.1:5432/postgres"
```

Start the API from the repository root:

```powershell
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## Run with Docker Compose

Start PostgreSQL, the API, and the dashboard from the repository root:

```powershell
docker compose up --build -d
```

Open the dashboard at `http://localhost:3000` and the API documentation at `http://localhost:8000/docs`. Compose uses a local development database password by default; set `POSTGRES_PASSWORD` in `.env` before starting if you need to change it. Stop the services with `docker compose down`.

## Frontend Setup

In a second terminal, install the frontend dependencies and start Vite:

```powershell
cd deadlock-dashboard
npm install vite
npm run dev
```

Open the URL printed by Vite, usually `http://localhost:5173`.

Useful frontend commands:

```powershell
npm run build
npm run lint
```

## API Routes

- `GET /` - Backend health check
- `GET /api/player/search?query=<name>` - Search for Steam players
- `GET /api/player/{account_id}/summary` - Retrieve or calculate player statistics

## Configuration and Security

Do not commit `.env` or real database credentials. Use `.env.example` as the template for local setup. The repository ignores virtual environments, dependency folders, caches, and frontend build output.

## Data Source

Player search, match history, and hero data are retrieved from the public [Deadlock API](https://deadlock-api.com/).
