# url-shortner

Paste a long link, get a short one. React + TypeScript frontend, FastAPI + Postgres backend,
Redis cache.

```
frontend/           React 19, Vite, Tailwind, shadcn/ui, TanStack Query (pnpm)
backend/            FastAPI, SQLAlchemy, Alembic (uv, Python 3.13)
docker-compose.yml  Postgres, Redis, backend and frontend
```

## How it works

- `POST /api/links` takes `{"url": "https://..."}` and returns the short link. Only `http`/`https`
  links up to 2083 characters, without a username or password, are accepted (`422` otherwise).
- `GET /{code}` redirects with a `302` to the original URL. It is a 302, not a 301, so clicks can
  be counted and links edited or expired later.
- Redirects are cached in Redis for an hour. If Redis is down, redirects fall back to Postgres.
- Errors are always JSON, and server errors carry a `request_id` that matches the server log.
  `GET /api/health` checks the process is up; `GET /api/health/ready` also checks Postgres.
- Not built yet: rate limiting and screening of malicious destinations.

## Setup

```bash
cp .env.example .env    # fill in POSTGRES_USER, POSTGRES_DB, POSTGRES_PASSWORD, REDIS_PASSWORD
docker compose up -d db redis
cd backend && uv run alembic upgrade head
```

Use letters and digits for passwords (`openssl rand -hex 16`): `$` and `#` are interpreted in
`.env` files. Use `127.0.0.1`, not `localhost`, for hosts: on Windows `localhost` can stall.

## Run

With Docker (app at http://localhost:8080, short links at http://localhost:8000):

```bash
docker compose up --build
```

Locally with hot reload:

```bash
cd backend  && uv run uvicorn app.main:app --reload   # http://127.0.0.1:8000, docs at /docs
cd frontend && pnpm install && pnpm dev                # http://127.0.0.1:5173
```

Vite and nginx both forward `/api` to the backend, so the browser uses one origin and needs no
CORS setup. Put every new API route under `/api`: any other path is treated as a short code.

## Checks

GitHub Actions runs the same checks on every pull request:

```bash
cd frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm build
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Dependency policy

- **frontend:** exact versions and a 3-week `minimumReleaseAge` (`frontend/pnpm-workspace.yaml`).
- **backend:** `uv.lock` pins everything, with `exclude-newer = "21 days"` and wheels only
  (`backend/pyproject.toml`).
