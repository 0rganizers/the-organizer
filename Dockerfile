FROM python:3.11-slim
WORKDIR /app

COPY poetry.lock /app/poetry.lock
COPY pyproject.toml /app/pyproject.toml
# not sure why, but poetry wants the README present.
COPY README.md /app/README.md

# install poetry because robin likes poems
RUN apt-get update && apt-get install -y curl
RUN pip install 'poetry==1.5.1' && poetry install --no-dev

# copy this over last to avoid having to rebuild docker just for code changes
COPY organizers_bot /app/organizers_bot
COPY config.json /app/config.json

#CMD /bin/sh
CMD poetry run organizers-bot
