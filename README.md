# url-shortner

Paste a long link, get a short one. React (Vite + TypeScript, Tailwind, shadcn/ui,
TanStack Query) frontend and FastAPI + Postgres backend.

```
url-shortner/
├── frontend/           React 19 + Vite + TypeScript (pnpm)
├── backend/            FastAPI + SQLAlchemy + Alembic (uv, Python 3.13)
└── docker-compose.yml  Postgres, backend and frontend as containers
```

## How it works

- `POST /api/links` with `{"url": "https://..."}` returns `{code, short_url, original_url, created_at}`.
  Only `http`/`https` links are accepted.
- `GET /{code}` answers with a `302` to the original URL. A 302 (not 301) so browsers keep
  asking the server, which is what click counts, expiry and edits will need.
- Codes are 7 random base62 characters. The unique constraint on `links.code` is the source of
  truth: on a collision the insert is retried with a new code.
- Short links are built from `BASE_URL` and served by the backend, not the frontend.

## Setup

```bash
cp .env.example .env
docker compose up -d db
cd backend && uv run alembic upgrade head
```

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

Vite proxies `/api` to the backend, so the browser talks to one origin and no CORS setup is
needed. Put every new API route under `/api`; anything else is treated as a short code.

## Run with Docker

```bash
docker compose up --build   # app at http://localhost:8080, short links at http://localhost:8000
docker compose down
```

A one-shot `migrate` service runs `alembic upgrade head` once and exits; the backend starts only
after it succeeds. The frontend
container serves the built app with nginx and forwards `/api` to the backend. Ports are published on
loopback only. The containers run non-root, read-only, with no extra capabilities.

## Checks

GitHub Actions runs `frontend.yml` and `backend.yml` (in `.github/workflows/`) on pull requests
and on pushes to `main`. To run the same checks locally:

```bash
cd frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm build
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Backend tests run against in-memory SQLite, so they need no database. Frontend tests use
Vitest (`pnpm test` runs once, `pnpm test:watch` re-runs on save); test files sit next to the
code they cover as `*.test.ts`.

## Dependency policy

- **frontend**: exact versions, and a 3-week `minimumReleaseAge` (`frontend/pnpm-workspace.yaml`).
- **backend**: `uv.lock` pins everything; `exclude-newer = "21 days"` and `no-build = true`
  (wheels only) in `backend/pyproject.toml`.
