# url-shortner

React (Vite + TypeScript) frontend and FastAPI backend.

```
url-shortner/
├── frontend/           React 19 + Vite + TypeScript (pnpm)
├── backend/            FastAPI + uvicorn (uv, Python 3.13)
└── docker-compose.yml  runs both as containers
```

## Run with Docker

```bash
docker compose up --build   # http://localhost:8080
docker compose down
```

The frontend container serves the built app with nginx and forwards `/api` to the
backend container. Only the frontend is published (loopback, port 8080). Both
containers run non-root, read-only, with no extra capabilities.

## Run locally (hot reload)

Backend, at http://127.0.0.1:8000 (API docs at `/docs`):

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Frontend, at http://127.0.0.1:5173:

```bash
cd frontend
pnpm install
pnpm dev
```

Both setups route `/api` to the backend (Vite proxy locally, nginx in Docker), so
the browser talks to a single origin and no CORS setup is needed. Put every new
route under `/api`.

## Dependency policy

- **frontend**: exact versions, and a 3-week `minimumReleaseAge` (`frontend/pnpm-workspace.yaml`).
- **backend**: `uv.lock` pins everything; `exclude-newer = "21 days"` and `no-build = true`
  (wheels only) in `backend/pyproject.toml`.

