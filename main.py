import io
import logging
import os
import pickle
import uuid
import json
from tempfile import NamedTemporaryFile
from typing import IO, Any, List, Optional

import beatmachine as bm
import cachetools
import xxhash
from beatmachine.effect_registry import Effect, EffectRegistry
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError, conint, conlist, validator
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

MAX_FILE_SIZE = int(os.getenv("BEATFUNC_MAX_FILE_SIZE") or 8000000)
ORIGINS = (os.getenv("BEATFUNC_ORIGINS") or "*").split(";")
ALLOW_YT = bool(int(os.getenv("BEATFUNC_ALLOW_YT") or 1))

if ALLOW_YT:
    import yt_dlp

logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    max_age=300,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class LRUFileCache(cachetools.LRUCache):
    def popitem(self):
        k, v = super().popitem()
        logger.info(f"Cache: evicting {k}")
        if os.path.isfile(v):
            os.remove(v)


# We keep the hash -> filename cache in memory because when our process dies, the container (and thus cached files) go
# with it
song_cache = LRUFileCache(maxsize=8)


class SettingsSchema(BaseModel):
    suggested_bpm: Optional[conint(gt=60, lt=300)] = None
    drift: Optional[conint(ge=0, lt=200)] = 15

    @property
    def max_bpm(self) -> int:
        if self.suggested_bpm is not None:
            return self.suggested_bpm + self.drift
        else:
            return 300

    @property
    def min_bpm(self) -> int:
        if self.suggested_bpm is not None:
            return self.suggested_bpm - self.drift
        else:
            return 60


def find_or_load_beats(filename: str, loader: bm.beats.loader.BeatLoader) -> bm.Beats:
    h = xxhash.xxh32()
    with open(filename, "rb") as file:
        block = file.read(512)
        while block:
            h.update(block)
            block = file.read(512)
    d = h.digest()

    if d in song_cache:
        logger.info(f"Using cached beats for song with hash {d}")
        try:
            return pickle.load(open(song_cache[d], "rb"))
        except:
            logger.error('Exception occurred while loading cached beats. Regenerating', exc_info=True)

    logger.info(f"Locating beats for song with hash {d}")
    beats = bm.Beats.from_song(filename, beat_loader=loader)
    beat_filename = f"{filename}_beats.pkl"

    with open(beat_filename, "wb") as fp:
        logger.info(f"Cached beats for song with hash {d} at {beat_filename}")
        pickle.dump(beats, fp)

    song_cache[d] = beat_filename

    return beats


async def process_song(effects: List[Effect], filename: str, settings: SettingsSchema) -> IO[bytes]:
    if os.path.getsize(filename) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    def load(f):
        return bm.loader.load_beats_by_signal(f, min_bpm=settings.min_bpm, max_bpm=settings.max_bpm)

    try:
        beats = find_or_load_beats(filename, loader=load)
    except Exception as e:
        logger.error(
            "An exception occurred while locating beats\n"
            f"  Settings: {settings}\n",
            exc_info=True
        )
        raise HTTPException(detail="Failed to locate beats", status_code=500) from e

    try:
        e = None  # so the name is always available in the exception handler below. kinda weird but whatever
        for e in effects:
            beats = beats.apply(e)
    except:
        effect_name = '<unknown effect>'

        if not e:
            effect_name = '<no effect>'
        elif hasattr(e, '__effect_name__'):
            effect_name = e.__effect_name__

        effect_infos = ', '.join([f'{e2} {e2.__dict__}' for e2 in effects])
        logger.error(
            "An exception occurred while applying an effect\n"
            f"  Settings: {settings}\n"
            f"  Effect ({effect_name}): {e} {e.__dict__}\n"
            f"  All effects: {effect_infos}\n",
            exc_info=True
        )

        raise HTTPException(detail=f"Failed to apply effect", status_code=500)

    buf = io.BytesIO()
    beats.save(buf, out_format="mp3")
    os.remove(filename)
    buf.seek(0)

    return buf


class JobSchema(BaseModel):
    settings: Optional[SettingsSchema] = SettingsSchema()
    effects: conlist(Any, min_items=1, max_items=5)

    @validator("effects", each_item=True)
    def instantiate_effects(cls, v):
        try:
            return EffectRegistry.load_effect(v)
        except ValueError as e:
            raise ValidationError("Failed to load effects", e)


@app.post("/")
async def handle_file_job(effects: str = Form(default=None), song: UploadFile = File(default=None)):
    try:
        job = JobSchema.parse_raw(effects)
    except ValidationError as e:
        logger.exception(e)
        raise HTTPException(detail=e.json(), status_code=422)

    with NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
        fp.write(await song.read())
        filename = fp.name

    return StreamingResponse(await process_song(job.effects, filename, job.settings), media_type="audio/mpeg")


class UrlJobSchema(JobSchema):
    url: str


@app.post("/yt")
async def handle_url_job(job: UrlJobSchema):
    if not ALLOW_YT:
        raise HTTPException(detail="YouTube downloads are disabled on this instance", status_code=404)

    try:
        base_filename = str(uuid.uuid4())
        with yt_dlp.YoutubeDL(
            {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "outtmpl": base_filename + ".mp4",
                "prefer_ffmpeg": True,
                "quiet": True,
            }
        ) as ydl:
            ydl.download([job.url])
    except Exception:
        raise HTTPException(detail="Failed to download video", status_code=400)

    return StreamingResponse(
        await process_song(job.effects, base_filename + ".mp3", job.settings),
        media_type="audio/mpeg",
    )
