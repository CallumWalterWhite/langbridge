"""Compatibility entrypoint for the API app."""
# TODO: Remove this shim after updating process managers to the new app path.
from langbridge.apps.api.langbridge_api.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "langbridge.apps.api.langbridge_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
