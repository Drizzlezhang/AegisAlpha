"""FastAPI application instance with CORS and router registration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis.api.routes import agents, health, pipeline, positions, recommendations, triggers

app = FastAPI(title="Aegis 2.0 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(positions.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")
app.include_router(triggers.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
