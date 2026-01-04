from contextlib import asynccontextmanager
import inspect

from fastapi import FastAPI
from fastapi.routing import APIRoute
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from api import api_router_v1
from config import settings
from db import initialize_database
from ioc import Container
from ioc.wiring import wire_packages
from utils.logger import setup_logging

from middleware import UnitOfWorkMiddleware, ErrorMiddleware, AuthMiddleware
from dotenv import load_dotenv

load_dotenv()

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
    init_result = container.init_resources()
    if inspect.isawaitable(init_result):
        await init_result
    initialize_database(container.engine())
    app.state.container = container
    yield
    shutdown_result = container.shutdown_resources()
    if inspect.isawaitable(shutdown_result):
        await shutdown_result

setup_logging(service_name=settings.PROJECT_NAME)

app = FastAPI(
    title=settings.PROJECT_NAME,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Order of middleware matters! UnitOfWork should be first to ensure DB session is available to all
# subsequent middleware and route handlers.
app.add_middleware(ErrorMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    https_only=False,
)
app.add_middleware(AuthMiddleware)
app.add_middleware(UnitOfWorkMiddleware)

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

FastAPIInstrumentor.instrument_app(app)

if __name__ == "__main__":
    import uvicorn

    host = getattr(settings, "HOST", "0.0.0.0")
    port = int(getattr(settings, "PORT", 8000))
    reload = bool(getattr(settings, "UVICORN_RELOAD", settings.IS_LOCAL))
    log_level = getattr(settings, "UVICORN_LOG_LEVEL", "info")

    # You can also set workers via env/CLI in production (e.g., `--workers 4`)
    uvicorn.run(
        "main:app",  # adjust module path if this file isn't named main.py
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        factory=False,
    )
