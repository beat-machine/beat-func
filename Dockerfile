FROM python:3.12 as wheel-builder

COPY poetry.lock pyproject.toml ./

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

RUN poetry export --without-hashes --without-urls > requirements.txt && \
    pip wheel -r requirements.txt -w /root/wheels

FROM python:3.12-slim

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends ffmpeg

COPY --from=wheel-builder /root/wheels /root/wheels
RUN pip install --no-cache-dir --no-deps /root/wheels/*.whl

WORKDIR /srv
COPY . .

ENV PORT 80
ENV BF__CORE__MAX_FILE_SIZE 8000000
ENV BF__SIMPLE__ORIGINS https://mystifying-heisenberg-1d575a.netlify.com;https://beatmachine.branchpanic.me;https://branchpanic.me
ENV BF__SIMPLE__ALOW_YT 1

# Uses the "beatfunc.simple" implementation
CMD uvicorn --host 0.0.0.0 --port ${PORT} beatfunc.simple.main:api
