FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LLM_MODE=stub

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY everstory ./everstory

RUN pip install --upgrade pip && pip install ".[web]" \
    && useradd --create-home --uid 10001 everstory \
    && mkdir -p /app/saves \
    && chown -R everstory:everstory /app

USER everstory
EXPOSE 8123

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8123/api/health', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "everstory.api.main:app", "--host", "0.0.0.0", "--port", "8123"]
