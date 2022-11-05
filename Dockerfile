FROM python:3.11-slim

ENV APP_HOME /srv
ENV PORT 80

ENV BEATFUNC_ORIGINS https://mystifying-heisenberg-1d575a.netlify.com;https://beatmachine.branchpanic.me;https://branchpanic.me
ENV BEATFUNC_MAX_FILE_SIZE 8000000
ENV BEATFUNC_ALLOW_YT 1

WORKDIR ${APP_HOME}
COPY . .

RUN set -x && \
    apt-get update && \
    apt-get install -y libopenblas-dev portaudio19-dev fftw-dev ffmpeg git build-essential curl

RUN set -x && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    /root/.local/bin/poetry config virtualenvs.create false && \
    /root/.local/bin/poetry install --only main --no-cache --no-root --no-interaction --no-ansi

CMD uvicorn --host 0.0.0.0 --port ${PORT} main:app
