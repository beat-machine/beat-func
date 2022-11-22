FROM python:3.11-slim

ENV APP_HOME /srv
ENV PORT 80

ENV BF__CORE__MAX_FILE_SIZE 8000000
ENV BF__SIMPLE__ORIGINS https://mystifying-heisenberg-1d575a.netlify.com;https://beatmachine.branchpanic.me;https://branchpanic.me
ENV BF__SIMPLE__ALOW_YT 1

WORKDIR ${APP_HOME}
COPY . .

RUN set -x && \
    apt-get update && \
    apt-get install -y libopenblas-dev portaudio19-dev fftw-dev ffmpeg git build-essential curl libsndfile1

# Uses the "beatfunc.simple" implementation
RUN set -x && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    /root/.local/bin/poetry config virtualenvs.create false && \
    /root/.local/bin/poetry install --only main --no-cache --no-root --no-interaction --no-ansi -E simple

CMD uvicorn --host 0.0.0.0 --port ${PORT} beatfunc.simple.main:api
