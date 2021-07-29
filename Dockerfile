FROM python:3.9-slim

RUN apt-get update && apt-get install -y curl
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | POETRY_HOME=/usr python -

CMD cd /app && poetry install --no-dev && poetry run organizers-bot
