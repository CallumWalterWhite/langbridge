from contextlib import asynccontextmanager
import inspect

from fastapi import FastAPI
from fastapi.routing import APIRoute
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from langbridge.apps.api.langbridge_api.routers import api_router_v1
from langbridge.packages.common.langbridge_common.config import settings
from langbridge.apps.api.langbridge_api.ioc import build_container
from langbridge.apps.api.langbridge_api.ioc.wiring import wire_packages
from langbridge.packages.common.langbridge_common.logging.logger import setup_logging
from langbridge.packages.common.langbridge_common.monitoring import (
    PrometheusMiddleware,
    metrics_response,
)

from langbridge.apps.api.langbridge_api.middleware import (
    UnitOfWorkMiddleware, 
    ErrorMiddleware, 
    AuthMiddleware, 
    RequestContextMiddleware,
    CorrelationIdMiddleware,
    MessageFlusherMiddleware
)
from dotenv import load_dotenv

load_dotenv()

def custom_generate_unique_id(route: APIRoute) -> str:
    if len(route.tags) == 0:
        return route.name
    return f"{route.tags[0]}-{route.name}"

container = build_container(settings)
wire_packages(
    container,
    package_names=[
        "langbridge.apps.api.langbridge_api.routers",
        "langbridge.apps.api.langbridge_api.services",
        "langbridge.apps.api.langbridge_api.repositories",
        "langbridge.apps.api.langbridge_api.auth",
        "langbridge.apps.api.langbridge_api.middleware",
    ],
    extra_modules=["langbridge.apps.api.langbridge_api.main"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to handle startup and shutdown events."""
    init_result = container.init_resources()
    if inspect.isawaitable(init_result):
        await init_result
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


# Middleware
# Middlewares are executed in the order they are added.
# So the first added middleware is the outermost layer.
app.add_middleware(ErrorMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    https_only=False,
)
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CorrelationIdMiddleware)
# Unit of Work Middleware should be after Auth Middleware to have access to user info
app.add_middleware(UnitOfWorkMiddleware)
app.add_middleware(PrometheusMiddleware, service_name="langbridge_api")
app.add_middleware(MessageFlusherMiddleware) 

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


@app.get("/metrics")
def metrics() -> Response:
    return metrics_response()

FastAPIInstrumentor.instrument_app(app)

if __name__ == "__main__":
    import uvicorn

    host = getattr(settings, "HOST", "0.0.0.0")
    port = int(getattr(settings, "PORT", 8000))
    reload = bool(getattr(settings, "UVICORN_RELOAD", settings.IS_LOCAL))
    log_level = getattr(settings, "UVICORN_LOG_LEVEL", "info")

    # You can also set workers via env/CLI in production (e.g., `--workers 4`)
    uvicorn.run(
        "langbridge.apps.api.langbridge_api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        factory=False,
    )
