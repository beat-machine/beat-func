FROM python:3.10-slim

ENV APP_HOME /srv
ENV PORT 80

ENV BEATFUNC_ORIGINS https://mystifying-heisenberg-1d575a.netlify.com;https://beatmachine.branchpanic.me
ENV BEATFUNC_MAX_FILE_SIZE 8000000
ENV BEATFUNC_ALLOW_YT 1

WORKDIR ${APP_HOME}
COPY . .

RUN set -x && \
    apt-get update && \
    apt-get install -y libopenblas-dev portaudio19-dev fftw-dev ffmpeg git

RUN set -x && \
    pip install -e git+https://github.com/CPJKU/madmom#egg=madmom && \
    pip install -r requirements.txt

CMD uvicorn --host 0.0.0.0 --port ${PORT} main:app
