import hashlib
import io
import logging
import pickle
import time
import typing as t
import uuid
from pathlib import Path

import yt_dlp
from beatmachine import Beats
from beatmachine.backend import Backend
from beatmachine.backends.madmom import MadmomDbnBackend
from beatmachine.effect_registry import Effect

from . import config
from . import exceptions as exc

logger = logging.getLogger("beatfunc.core")
logger.propagate = True


def _load_beats_cached(audio_file: Path, backend: Backend) -> Beats:
    md5 = hashlib.md5()
    with audio_file.open("rb") as file:
        while block := file.read(512):
            md5.update(block)

    cached_beats = config.CACHE_PATH / (md5.hexdigest())

    if cached_beats.is_file():
        try:
            return pickle.load(open(cached_beats, "rb"))
        except:
            logger.exception("Failed to load cached beats at %s, regenerating", cached_beats)

    beats = Beats.from_song(str(audio_file), backend=backend)

    with cached_beats.open("wb") as fp:
        pickle.dump(beats, fp)

    return beats


def download_song(url: str) -> Path:
    audio_file = (config.DOWNLOAD_PATH / uuid.uuid4().hex).with_suffix(".mp3")

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
            "outtmpl": str(audio_file.with_suffix("")),
            "prefer_ffmpeg": True,
            "quiet": True,
        }
    ) as ydl:
        ydl.download([url])

    return audio_file


def process_song_file(audio_file: Path, effects: t.List[Effect], min_bpm: int, max_bpm: int) -> t.BinaryIO:
    logger.info("Processing song at %s", audio_file)
    start = time.time()

    backend = MadmomDbnBackend(min_bpm, max_bpm, model_count=4)

    try:
        if audio_file.stat().st_size > config.MAX_FILE_SIZE:
            logger.warning("Song is larger than allowed max of %i bytes", config.MAX_FILE_SIZE)
            raise exc.SongTooLargeException(config.MAX_FILE_SIZE)

        try:
            beats = _load_beats_cached(audio_file, backend)
        except Exception as e:
            logger.exception("Couldn't load song")
            raise exc.LoadException("Couldn't load song") from e

        logger.info("Load finished after %2.2f sec since start", time.time() - start)

        for effect in effects:
            try:
                beats = beats.apply(effect)
            except Exception as e:
                logger.exception("Failed to apply effect to song")
                raise exc.EffectException(effect) from e

        buf = io.BytesIO()
        beats.save(buf, out_format="mp3")
        buf.seek(0)

        logger.info("Processing finished after %2.2f sec since start", time.time() - start)
        return buf
    finally:
        logger.debug("Removing cached song")
        audio_file.unlink()


def process_song_url(url: str, effects: t.List[Effect], min_bpm: int, max_bpm: int) -> t.BinaryIO:
    logger.info("Downloading song from %s", url)

    try:
        audio_file = download_song(url)
    except Exception as e:
        logger.exception("Download failed for song at %s", url)
        raise exc.DownloadException(url) from e

    return process_song_file(audio_file, effects, min_bpm, max_bpm)
