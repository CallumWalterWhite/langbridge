# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy the langbridge package so imports work when running the proxy module.
COPY langbridge /app/langbridge

# No external dependencies required for the proxy; if you add any, install here.

EXPOSE 55432 53306

CMD ["python", "-m", "langbridge.proxy.app"]
