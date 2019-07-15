FROM python:3.7

ENV APP_HOME /srv
ENV PORT 80

WORKDIR ${APP_HOME}
COPY . .

RUN set -x && \
    apt-get update && \
    apt-get install -y libopenblas-dev portaudio19-dev fftw-dev ffmpeg

RUN set -x && \
    pip install --no-cache cython numpy && \
    pip install --no-cache -r requirements.txt

CMD uvicorn --bind :${PORT} main:app
