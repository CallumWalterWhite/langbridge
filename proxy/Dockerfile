# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy the proxy sources into the image.
COPY . /app

# No external dependencies required for the proxy; if you add any, install here.

EXPOSE 55432 53306 51433

CMD ["python", "app.py"]
