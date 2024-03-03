FROM python:3.9.18-bookworm

WORKDIR /usr/src/mujoco-sandbox

ENV POETRY_CACHE_DIR=/tmp/poetry_cache \
    POETRY_NO_INTERACTION=1

RUN pip install poetry==1.8.1

COPY pyproject.toml poetry.lock ./

RUN poetry install --without dev

COPY . .

ENTRYPOINT ["poetry", "run", "python"]

CMD ["src/main.py"]
