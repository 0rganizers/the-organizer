FROM python:3.9-alpine

RUN apk add curl
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python -

CMD cd /app && poetry install --no-dev && poetry run organizers-bot
