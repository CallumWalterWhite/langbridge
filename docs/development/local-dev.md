# Local Development

## Python Environment

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .\.venv\Scripts\activate  # Windows PowerShell
pip install -r langbridge/requirements.txt
```

## Run The Runtime Worker

```bash
python -m langbridge.apps.runtime_worker.main
```

## Run The Local Runtime Stack

```bash
docker compose up --build db redis worker
```

## Testing

```bash
pytest -q tests/unit
```
