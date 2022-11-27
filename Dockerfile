FROM python:3.11-slim

RUN set -x && \
    apt-get update && \
    apt-get install -y libopenblas-dev portaudio19-dev fftw-dev ffmpeg git libsndfile1 gcc g++

RUN set -x && \
    pip install poetry && \
    poetry config virtualenvs.create false

ENV APP_HOME /srv
WORKDIR ${APP_HOME}

COPY poetry.lock pyproject.toml ./

RUN set -x && \
    poetry install --only main --no-cache --no-root --no-interaction --no-ansi -E simple

COPY . .

ENV PORT 80
ENV BF__CORE__MAX_FILE_SIZE 8000000
ENV BF__SIMPLE__ORIGINS https://mystifying-heisenberg-1d575a.netlify.com;https://beatmachine.branchpanic.me;https://branchpanic.me
ENV BF__SIMPLE__ALOW_YT 1

# Uses the "beatfunc.simple" implementation
CMD uvicorn --host 0.0.0.0 --port ${PORT} beatfunc.simple.main:api
