FROM python:3.9-slim
WORKDIR /app

COPY organizers_bot /app/organizers_bot
COPY config.json /app/config.json
COPY poetry.lock /app/poetry.lock
COPY pyproject.toml /app/pyproject.toml
# not sure why, but poetry wants the README present.
COPY README.md /app/README.md

# install poetry because robin likes poems
RUN apt-get update && apt-get install -y curl
RUN pip install 'poetry==1.1.13' && poetry install --no-dev

#CMD /bin/sh
CMD poetry run organizers-bot
