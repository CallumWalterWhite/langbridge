from typing import List

from fastapi import APIRouter

from .agents import router as agents_router
from .auth import router as auth_router
from .organizations import router as organizations_router
from .connectors import router as connectors_router
from .semantic_models import router as semantic_model_router

v1_routes: List[APIRouter] = [
    auth_router,
    agents_router,
    organizations_router,
    connectors_router,
    semantic_model_router,
]

__all__ = [
    "auth_router",
    "agents_router",
    "organizations_router",
    "connectors_router",
    "semantic_model_router",
    "v1_routes",
]
