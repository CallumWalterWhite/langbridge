from typing import List

from fastapi import APIRouter

from .agents import router as agents_router
from .auth import router as auth_router
from .chat import router as chat_router
from .datasources import router as datasources_router

v1_routes: List[APIRouter] = [
    auth_router,
    datasources_router,
    agents_router,
    chat_router,
]

__all__ = [
    "auth_router",
    "datasources_router",
    "agents_router",
    "chat_router",
    "v1_routes",
]
