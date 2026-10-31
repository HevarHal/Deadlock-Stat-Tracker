# Deadlock Tracker frontend

Vite serves the dashboard in `index.html`. Player lookup, match pagination, and scope switching live in `src/profile-app.js`. Hero palettes are defined in `src/hero-palettes.json` and applied by `src/hero-theme.js`.

Styles live in `public/dashboard.css`; hero catalogs, WebP renders, and their source attribution live in `public/assets/`.

Run `npm install` once, then `npm run dev` with the backend at `http://127.0.0.1:8000`. The development server proxies `/api` requests to the backend.

Use `npm run build` for the production bundle and `npm run lint` to check JavaScript. From the repository root, `docker compose up -d --build` starts the complete local stack.