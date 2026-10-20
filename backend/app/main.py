from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="url-shortner API")

# Everything the frontend calls lives under /api, so the Vite dev proxy can
# forward a single prefix and no CORS configuration is needed.
app.include_router(health.router, prefix="/api")
