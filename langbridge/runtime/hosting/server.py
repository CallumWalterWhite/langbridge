from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from langbridge.runtime.hosting.app import (
    _CONFIG_PATH_ENV,
    create_runtime_api_app,
)


def run_runtime_api(
    *,
    config_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    if reload:
        os.environ[_CONFIG_PATH_ENV] = str(Path(config_path).resolve())
        uvicorn.run(
            "runtime.hosting.app:create_runtime_api_app_from_env",
            host=host,
            port=port,
            reload=True,
            factory=True,
        )
        return

    app = create_runtime_api_app(config_path=config_path)
    uvicorn.run(app, host=host, port=port, reload=False)
