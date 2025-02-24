"""Main application module for Astral API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.components.authentication import router as authentication_router
from app.components.health import router as health_router
from app.components.location_proofs import router as location_proofs_router

app = FastAPI(
    title="Astral API",
    description="A decentralized geospatial data API with EAS integration",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(
    location_proofs_router, prefix=""
)  # Mount at root for OGC API compliance
app.include_router(authentication_router)
