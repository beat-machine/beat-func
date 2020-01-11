import http
import io
import json
import logging
import os
import timeit
import uuid
from tempfile import NamedTemporaryFile, mkstemp

import beatmachine as bm
import ffmpeg
import youtube_dl
from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse, JSONResponse
from typing import List
from pydantic import BaseModel
from mutagen.mp3 import MP3, MutagenError

MAX_LENGTH = 60 * 6 + 30

ORIGINS = [
    "https://mystifying-heisenberg-1d575a.netlify.com",
    "https://beatmachine.branchpanic.me",
    "https://tbm.branchpanic.me",
]

if os.getenv("BEATFUNC_ALL_ORIGINS"):
    ORIGINS = ["*"]

logger = logging.getLogger("beatfunc")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    max_age=300,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def _settings_to_kwargs(settings: dict) -> dict:
    kwargs = {"min_bpm": 60, "max_bpm": 300}

    if "suggested_bpm" in settings:
        suggested_bpm = settings["suggested_bpm"]
        drift = settings.pop("drift", 15)
        kwargs["min_bpm"] = suggested_bpm - drift
        kwargs["max_bpm"] = suggested_bpm + drift

    return kwargs


async def process_song(
    effects: List[bm.effects.base.BaseEffect], filename: str, processing_args: dict
):  
    try:
        metadata = MP3(filename)
    except MutagenError:
        raise HTTPException(status_code=http.HTTPStatus.UNPROCESSABLE_ENTITY, detail='Failed to read song metadata')

    if metadata.info.length > MAX_LENGTH:
        raise HTTPException(status_code=http.HTTPStatus.UNPROCESSABLE_ENTITY, detail=f'Song is too long (max is {MAX_LENGTH} seconds)')

    start_time = timeit.default_timer()
    logger.info(f"Starting with settings: {processing_args}")

    def load(f):
        return bm.loader.load_beats_by_signal(f, **processing_args)

    logger.info(f"Splitting and processing song")
    beats = bm.Beats.from_song(filename, loader=load)

    for e in effects:
        beats = beats.apply(e)

    buf = io.BytesIO()
    beats.consolidate().export(buf, format="mp3")
    os.remove(filename)
    elapsed = timeit.default_timer() - start_time
    logger.info(f"Finished in {elapsed}s, streaming result to client")
    buf.seek(0)

    return StreamingResponse(buf, media_type="audio/mpeg")


class YoutubeSongPayload(BaseModel):
    youtube_url: str
    effects: List[dict]
    settings: dict


@app.post("/yt")
async def process_song_from_youtube(payload: YoutubeSongPayload):
    try:
        effects = [bm.effects.load_from_dict(e) for e in payload.effects]
    except TypeError as e:
        logger.error(f"Invalid effect data: {e}")
        raise HTTPException(
            detail="Invalid effect data", status_code=http.HTTPStatus.BAD_REQUEST
        )

    logger.info("Downloading file")

    try:
        base_filename = str(uuid.uuid4())
        with youtube_dl.YoutubeDL({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': base_filename + ".mp4",
            'prefer_ffmpeg': True,
            'quiet': True,
        }) as ydl:
            ydl.download([payload.youtube_url])
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            detail="Failed to download video", status_code=http.HTTPStatus.BAD_REQUEST
        )

    return await process_song(
        effects, base_filename + ".mp3", _settings_to_kwargs(payload.settings)
    )


@app.post("/")
async def process_song_from_file(
    effects: str = Form(default=None), song: UploadFile = File(default=None)
):
    logger.info("Received song data")
    try:
        effect_data = json.loads(effects)
        settings = {}

        if isinstance(effect_data, dict):
            settings = effect_data.pop("settings", {})
            effect_data = effect_data["effects"]

        try:
            effects = [bm.effects.load_from_dict(e) for e in effect_data]
        except TypeError as e:
            logger.error(f"Invalid effect data: {e}")
            raise HTTPException(
                detail="Invalid effect data", status_code=http.HTTPStatus.BAD_REQUEST
            )
    except KeyError as e:
        logger.error(f"KeyError when parsing JSON, assuming missing data: {e}")
        raise HTTPException(
            detail="Missing effects", status_code=http.HTTPStatus.BAD_REQUEST
        )
    except ValueError as e:
        logger.error(f"ValueError when parsing JSON, assuming malformed data: {e}")
        raise HTTPException(
            detail="Invalid effects", status_code=http.HTTPStatus.BAD_REQUEST
        )

    if len(effects) > 5:
        raise HTTPException(
            detail="Too many effects (max is 5)",
            status_code=http.HTTPStatus.BAD_REQUEST,
        )
    if len(effects) < 1:
        raise HTTPException(
            detail="Not enough effects (min is 1)",
            status_code=http.HTTPStatus.BAD_REQUEST,
        )

    with NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
        fp.write(await song.read())
        filename = fp.name

    return await process_song(effects, filename, _settings_to_kwargs(settings))
