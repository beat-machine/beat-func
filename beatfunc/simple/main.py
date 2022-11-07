import logging
import sys
from http import HTTPStatus
from pathlib import Path
from tempfile import NamedTemporaryFile

import fastapi as fa
import pydantic as pd
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from .. import core
from . import config
from .schemas import JobSchema, UrlJobSchema

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

logger = logging.getLogger("beatfunc.simple")
logger.propagate = True

api = fa.FastAPI(docs_url=None, redoc_url=None)
api.add_middleware(
    CORSMiddleware,
    allow_origins=config.ORIGINS,
    allow_credentials=True,
    max_age=300,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@api.post("/")
async def handle_file_job(effects: str = fa.Form(default=None), song: fa.UploadFile = fa.File(default=None)):
    try:
        job = JobSchema.parse_raw(effects)
    except pd.ValidationError as e:
        logger.exception("Validation error while parsing effects")
        raise fa.HTTPException(detail=e.json(), status_code=422)

    with NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
        fp.write(await song.read())
        audio_file = Path(fp.name)

    try:
        result = core.jobs.process_song_file(audio_file, job.effects, job.settings.min_bpm, job.settings.max_bpm)
    except core.exceptions.BeatFuncException as e:
        raise fa.HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e

    return StreamingResponse(result, media_type="audio/mpeg")


@api.post("/yt")
async def handle_url_job(job: UrlJobSchema):
    if not config.ALLOW_URLS:
        raise fa.HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="URL downloads are disabled on this instance")

    try:
        result = core.jobs.process_song_url(job.url, job.effects, job.settings.min_bpm, job.settings.max_bpm)
    except core.exceptions.BeatFuncException as e:
        raise fa.HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e

    return StreamingResponse(result, media_type="audio/mpeg")
