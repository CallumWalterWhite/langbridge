from fastapi import APIRouter

from .v1 import v1_routes
from langbridge.apps.api.langbridge_api.ioc import Container

api_router_v1 = APIRouter()
for route in v1_routes:
    api_router_v1.include_router(route)

__all__ = ["api_router_v1", "v1_routes"]