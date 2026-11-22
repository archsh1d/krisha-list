FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md requirements.lock ./
COPY src ./src
COPY web/dist ./web/dist
COPY deploy ./deploy
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir --no-deps -e . \
    && useradd --uid 10001 --create-home app \
    && mkdir -p /app/data \
    && chown app:app /app/data

USER app
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/v1/openapi.json', timeout=3).close()" || exit 1
CMD ["python", "deploy/run_server.py"]
