# syntax=docker/dockerfile:1

#stage 1 build
FROM python:3.12-slim-bookworm as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir poetry==2.4.1


ENV POETRY_NO_INTERACTION=true \  
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_CREATE=true 

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install --only main --no-root 

RUN find /app/.venv -depth -type d -name "__pycache__" -exec rm -rf {} + ; \
    find /app/.venv -type f -name "*.pyc" -delete ; \
    cd /app/.venv/lib/python3.12/site-packages/botocore/data 2>/dev/null \
    && find . -maxdepth 1 -mindepth 1 -type d ! -name s3 ! -name sts -exec rm -rf {} + || true





#stage 2 runtime
FROM python:3.12-slim-bookworm AS runtime

ARG GIT_SHA=dev
ARG BUILD_DATE=1970-01-01T00:00:00Z
LABEL org.opencontainers.image.title="bot-service" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}"


RUN groupadd --system --gid 1001 app \ 
    && useradd --system --uid 1001 --gid app --no-create-home app
    
    
ENV PYTHONUNBUFFERED=true \
    PYTHONDONTWRITEBYTECODE=true \
    PYTHONPATH="/app" \
    PATH="/app/.venv/bin:$PATH" 

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app . . 

USER 1001:1001




ENTRYPOINT ["python"]
CMD ["main.py"]
