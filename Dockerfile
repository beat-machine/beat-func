FROM python:3.7.5-slim

ENV APP_HOME /srv
ENV PORT 80

WORKDIR ${APP_HOME}
COPY . .

RUN set -x && \
    apt-get update && \
    apt-get install -y libopenblas-dev portaudio19-dev fftw-dev ffmpeg

RUN set -x && \
    pip install --no-cache poetry && \
    poetry config virtualenvs.create false && \
    poetry install

CMD uvicorn --host 0.0.0.0 --port ${PORT} main:app
