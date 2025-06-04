FROM python:3.12-slim as requirements-stage
WORKDIR /tmp

RUN pip install poetry==2.1.3

RUN poetry self add poetry-plugin-export

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

COPY ./pyproject.toml ./poetry.lock* /tmp/

RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --with dev --without metrics

FROM python:3.12-slim as build-stage
WORKDIR /app
RUN apt update && apt install -y --no-install-recommends make

COPY --from=requirements-stage ./tmp/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

COPY secrets-entrypoint.sh /app/secrets-entrypoint.sh

USER 10000

ENTRYPOINT [ "/app/secrets-entrypoint.sh" ]
