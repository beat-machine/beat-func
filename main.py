import http
import io
import json
import logging
import os
import timeit
from tempfile import NamedTemporaryFile, mkstemp

import beatmachine as bm
import ffmpeg
from fastapi import FastAPI, Form, File, UploadFile
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse
from typing import List
from pytube import YouTube
from pydantic import BaseModel

logger = logging.getLogger("beatfunc")

app = FastAPI()

origins = [
    "https://mystifying-heisenberg-1d575a.netlify.com",
    "https://beatmachine.branchpanic.me",
]

if os.getenv("BEATFUNC_ALL_ORIGINS"):
    origins = ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)


async def process_song(
    effects: List[bm.effects.base.BaseEffect], filename: str, processing_args: dict
):
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
        return "Invalid effect data", http.HTTPStatus.BAD_REQUEST

    logger.info("Downloading file")
    raw_filename = (
        YouTube(payload.youtube_url).streams.filter(only_audio=True).first().download()
    )
    mp3_filename = str(uuid.uuid4())

    logger.info("Converting to mp3")
    ffmpeg.input(raw_filename).output(mp3_filename).run()
    os.remove(raw_filename)

    return await process_song(effects, mp3_filename, payload.settings)


@app.post("/")
async def process_song_from_file(
    effects: str = Form(default=None), song: UploadFile = File(default=None)
):
    logger.info("Received song data")
    try:
        effect_data = json.loads(effects)
        settings = {}

        if isinstance(effect_data, dict):
            settings = effect_data["settings"]
            effect_data = effect_data["effects"]

        try:
            effects = [bm.effects.load_from_dict(e) for e in effect_data]
        except TypeError as e:
            logger.error(f"Invalid effect data: {e}")
            return "Invalid effect data", http.HTTPStatus.BAD_REQUEST
    except KeyError as e:
        logger.error(f"KeyError when parsing JSON, assuming missing data: {e}")
        return "Missing effects", http.HTTPStatus.BAD_REQUEST
    except ValueError as e:
        logger.error(f"ValueError when parsing JSON, assuming malformed data: {e}")
        return "Invalid effects", http.HTTPStatus.BAD_REQUEST

    if len(effects) > 5:
        return "Too many effects (max is 5)", http.HTTPStatus.BAD_REQUEST
    if len(effects) < 1:
        return "Not enough effects (min is 1)", http.HTTPStatus.BAD_REQUEST

    with NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
        fp.write(await song.read())
        filename = fp.name

    kwargs = {"min_bpm": 60, "max_bpm": 300}

    if "suggested_bpm" in settings:
        suggested_bpm = settings["suggested_bpm"]
        drift = settings.pop("drift", 15)
        kwargs["min_bpm"] = suggested_bpm - drift
        kwargs["max_bpm"] = suggested_bpm + drift

    return await process_song(effects, filename, kwargs)
