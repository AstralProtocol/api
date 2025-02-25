from .authentication import router as authentication_router
from .health import router as health_router
from .location_proofs import router as location_proofs_router

__all__ = ["health_router", "location_proofs_router", "authentication_router"]
