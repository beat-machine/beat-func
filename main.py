import io
import ujson as json
import os
import uuid

from tempfile import NamedTemporaryFile, mkstemp

import beatmachine as bm

from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse, JSONResponse

from typing import Any, List, Optional, IO

from mutagen.mp3 import MP3
from mutagen import MutagenError

from pydantic import BaseModel, conlist, conint, validator, ValidationError

import logging
import cachetools
import xxhash
import pickle

MAX_LENGTH = int(os.getenv("BEATFUNC_MAX_LENGTH"))
ORIGINS = os.getenv("BEATFUNC_ORIGINS").split(";")
ALLOW_YT = bool(int(os.getenv("BEATFUNC_ALLOW_YT")))

if ALLOW_YT:
    import youtube_dl

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

EffectList = List[bm.effects.base.LoadableEffect]


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
        logger.info(f"Cache: hit {d}")
        try:
            return pickle.load(open(song_cache[d], "rb"))
        except Exception as e:
            logger.exception(f"Cache: failed to load {d}, falling through to miss", e)

    logger.info(f"Cache: miss {d}, creating...")
    beats = bm.Beats.from_song(filename, beat_loader=loader)
    beat_filename = f"{filename}_beats.pkl"

    with open(beat_filename, "wb") as fp:
        logger.info(f"Cache: creating entry {d} at {beat_filename}")
        pickle.dump(beats, fp)

    song_cache[d] = beat_filename

    return beats


async def process_song(
    effects: EffectList, filename: str, settings: SettingsSchema
) -> IO[bytes]:
    try:
        metadata = MP3(filename)
    except MutagenError as e:
        logger.exception(e)
        raise HTTPException(422, detail="Failed to parse song metadata")

    if metadata.info.length > MAX_LENGTH:
        logger.exception(e)
        raise HTTPException(413, detail="Song exceeded maximum length in seconds")

    def load(f):
        return bm.loader.load_beats_by_signal(
            f, min_bpm=settings.min_bpm, max_bpm=settings.max_bpm
        )

    beats = find_or_load_beats(filename, loader=load)

    for e in effects:
        beats = beats.apply(e)

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
            return bm.effects.load_from_dict(v)
        except ValueError as e:
            raise ValidationError("Failed to load effects", e)


@app.post("/")
async def handle_file_job(
    effects: str = Form(default=None), song: UploadFile = File(default=None)
):
    try:
        job = JobSchema.parse_raw(effects)
    except ValidationError as e:
        logger.exception(e)
        raise HTTPException(detail=e.json(), status_code=422)

    with NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
        fp.write(await song.read())
        filename = fp.name

    return StreamingResponse(
        await process_song(job.effects, filename, job.settings), media_type="audio/mpeg"
    )


class UrlJobSchema(JobSchema):
    url: str


@app.post("/yt")
async def handle_url_job(job: UrlJobSchema):
    if not ALLOW_YT:
        raise HTTPException(
            detail="YouTube downloads are disabled on this instance", status_code=404
        )

    try:
        base_filename = str(uuid.uuid4())
        with youtube_dl.YoutubeDL(
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
