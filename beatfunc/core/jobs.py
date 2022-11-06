import hashlib
import io
import logging
import pickle
import typing as t
import uuid
from pathlib import Path

import yt_dlp
from beatmachine import Beats
from beatmachine.effect_registry import Effect
from beatmachine.loader import BeatLoader, load_beats_by_signal

from . import exceptions as exc
from . import config

logger = logging.getLogger(__name__)




def _load_beats_cached(audio_file: Path, loader: BeatLoader) -> Beats:
    md5 = hashlib.md5()
    with audio_file.open("rb") as file:
        while block := file.read(512):
            md5.update(block)

    cached_beats = config.CACHE_PATH / (md5.hexdigest())

    if cached_beats.is_file():
        logger.info(f"Reusing cached beats at {cached_beats}")
        try:
            return pickle.load(open(cached_beats, "rb"))
        except:
            logger.error("Exception occurred while loading cached beats, regenerating", exc_info=True)

    beats = Beats.from_song(str(audio_file), beat_loader=loader)

    with cached_beats.open("wb") as fp:
        pickle.dump(beats, fp)

    return beats


def process_song_file(audio_file: Path, effects: t.List[Effect], min_bpm: int, max_bpm: int) -> t.BinaryIO:
    def loader(f):
        return load_beats_by_signal(f, min_bpm=min_bpm, max_bpm=max_bpm)

    try:
        if audio_file.stat().st_size > config.MAX_FILE_SIZE:
            raise exc.SongTooLargeException(config.MAX_FILE_SIZE)

        try:
            beats = _load_beats_cached(audio_file, loader=loader)
        except Exception as e:
            raise exc.LoadException() from e

        for effect in effects:
            try:
                beats = beats.apply(effect)
            except Exception as e:
                raise exc.EffectException(effect) from e

        buf = io.BytesIO()
        beats.save(buf, out_format="mp3")
        buf.seek(0)
        return buf
    finally:
        audio_file.unlink()


def process_song_url(url: str, effects: t.List[Effect], min_bpm: int, max_bpm: int) -> t.BinaryIO:
    try:
        audio_file = config.DOWNLOAD_PATH / uuid.uuid4().hex
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
                "outtmpl": audio_file.with_suffix("mp4"),
                "prefer_ffmpeg": True,
                "quiet": True,
            }
        ) as ydl:
            ydl.download([url])
    except Exception as e:
        raise exc.DownloadException(url) from e

    return process_song_file(audio_file, effects, min_bpm, max_bpm)
