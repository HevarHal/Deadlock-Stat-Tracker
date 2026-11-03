# Development guide

## Where features belong

| Area | Files | Responsibility |
| --- | --- | --- |
| API routes and scopes | `main.py` | Player search, match history, summary responses, application lifecycle |
| Summary calculations | `metrics.py` | Pure calculations; no HTTP or database access |
| Upstream requests | `upstream.py` | Shared HTTP client, request deduplication, bounded JSON cache |
| Match details | `match_details.py` | Item purchases and starting guide lookups |
| Persistence | `database.py` | PostgreSQL models, sessions, schema initialization |
| Profile interface | `deadlock-dashboard/src/profile-app.js` | Search, profile loading, filters, pagination |
| Player URLs | `deadlock-dashboard/src/player-route.js` | Name encoding, URL parsing, exact-name matching |
| Match presentation | `deadlock-dashboard/src/match-table.js`, `match-build.js` | Match rows, rank badges, expandable item timelines and guides |
| Appearance | `deadlock-dashboard/public/dashboard.css`, `src/hero-theme.js` | Layout and hero themes |

Keep calculations separate from I/O so they can be tested without external services.
Use `client_for(request)` for upstream calls instead of creating clients inside routes.
The application owns the HTTP client's lifetime and closes shared requests at shutdown.

## State and cache rules

- The player URL identifies the profile. There is no session-storage dependency.
- Browser history retains the selected account to distinguish duplicate names within a tab. A shared name URL may need a player picker.
- Scope and match-history pagination reset on refresh.
- Upstream search is uncached. Successful JSON responses use a 60-second lifetime, or one hour for asset catalogs.
- The cache is per application worker, limited to 128 entries and 32 MiB of serialized response bodies. Parsed objects consume additional memory.
- Season 1 summaries in PostgreSQL expire against the original history fetch time; saving a summary must not extend freshness.
- A recorded build value is not enough to display a Build ID. It must resolve to a guide; use the returned `hero_build_id`. Missing guides must not hide item purchases.

## Checks

From the repository root:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m ruff check main.py database.py upstream.py metrics.py match_details.py tests scripts
.venv\Scripts\python.exe -m ruff format --check main.py database.py upstream.py metrics.py match_details.py tests scripts
```

From `deadlock-dashboard`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

Python tests mock upstream and database access. Frontend controller tests use a small DOM fixture and mocked API responses; they do not replace browser testing.

## Generated files and cleanup

`deadlock-dashboard/dist`, Python `__pycache__` directories, `.ruff_cache`, and
`node_modules/.vite` are generated and can be recreated. Stop a preview that serves
`dist` before removing that directory. Dependencies in `.venv` and `node_modules`
are needed for local development and should not be treated as unused files.

`.work-perf` holds local benchmark evidence, deployment scripts, and rollback
snapshots. Temporary upload archives and completed diagnostic scripts can be removed;
retain before/after measurements and rollback snapshots until no longer needed.
Keep secrets, PostgreSQL volumes, hero artwork, asset attribution, and deployment
backups separate from generated-file cleanup. Docker images used by running services
and rollback images are not disposable build caches.
