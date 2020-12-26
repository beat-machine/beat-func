FROM python:3.7.5-slim

ENV APP_HOME /srv
ENV PORT 80

ENV BEATFUNC_ORIGINS https://mystifying-heisenberg-1d575a.netlify.com;https://beatmachine.branchpanic.me
ENV BEATFUNC_MAX_LENGTH 390
ENV BEATFUNC_ALLOW_YT 0

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
