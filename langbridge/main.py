from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api import api_router_v1
from config import settings
from db import initialize_database
from ioc import Container
from ioc.wiring import wire_packages
from utils.logger import setup_file_logging

from middleware import UnitOfWorkMiddleware, ErrorMiddleware, AuthMiddleware

def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"

container = Container()
wire_packages(
    container,
    package_names=["api", "services", "repositories", "auth", "middleware"],  # add more roots as needed
    extra_modules=["main"],  # optional: single modules to wire
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to handle startup and shutdown events."""
    container.init_resources()
    initialize_database(container.engine())
    app.state.container = container

    yield

    container.shutdown_resources()


app = FastAPI(
    title=settings.PROJECT_NAME,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)


if settings.IS_LOCAL:
    setup_file_logging()


# Order of middleware matters! UnitOfWork should be first to ensure DB session is available to all
# subsequent middleware and route handlers.
app.add_middleware(UnitOfWorkMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    https_only=False, 
)
app.add_middleware(ErrorMiddleware)

if settings.CORS_ENABLED:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )


app.include_router(
    api_router_v1,
    prefix=settings.API_V1_STR,
)
