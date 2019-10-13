import http
import io
import json
import logging
import os
import timeit
from tempfile import NamedTemporaryFile

import beatmachine as bm
from fastapi import FastAPI, Form, File
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

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


@app.post("/")
async def process_song(
    effects: str = Form(default=None), song: bytes = File(default=None)
):
    logger.info("Received song data")
    try:
        effect_data = json.loads(effects)
        settings = {}

        if isinstance(effect_data, dict):
            settings = effect_data["settings"]
            effect_data = effect_data["effects"]

        effects = [bm.effects.load_from_dict(e) for e in effect_data]
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
        fp.write(song)
        filename = fp.name

    kwargs = {"min_bpm": 60, "max_bpm": 300}

    if "suggested_bpm" in settings:
        suggested_bpm = settings["suggested_bpm"]
        drift = settings.pop("drift", 15)
        kwargs["min_bpm"] = suggested_bpm - drift
        kwargs["max_bpm"] = suggested_bpm + drift

    start_time = timeit.default_timer()
    logger.info(f"Starting processing with settings: {kwargs}")

    beats = bm.loader.load_beats_by_signal(filename, **kwargs)
    edited_beats = bm.editor.apply_effects(beats, effects)
    logger.info(f"Generator created, beginning render")

    buf = io.BytesIO()
    sum(list(edited_beats)).export(buf, format="mp3")
    elapsed = timeit.default_timer() - start_time
    logger.info(f"Finished in {elapsed}s, streaming result to client")
    buf.seek(0)

    return StreamingResponse(buf, media_type="audio/mpeg")
