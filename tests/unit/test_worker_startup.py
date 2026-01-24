import os


def test_worker_run_once(monkeypatch) -> None:
    monkeypatch.setenv("WORKER_RUN_ONCE", "true")
    monkeypatch.setenv("WORKER_POLL_INTERVAL", "0")
    monkeypatch.setenv("WORKER_BROKER", "noop")
    from langbridge.apps.worker.langbridge_worker import main as worker_main

    worker_main.main()
