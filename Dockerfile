FROM python:3.12-slim


RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev && \
    rm -rf /var/lib/apt/lists/*


WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && \ 
    poetry install --no-interaction --no-ansi --no-root


COPY . .

CMD poetry run python main.py