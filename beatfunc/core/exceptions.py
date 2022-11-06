import typing as t

from beatmachine.effect_registry import Effect


class BeatFuncException(Exception):
    pass


class DownloadException(BeatFuncException):
    def __init__(self, url: str) -> None:
        super().__init__(f"Failed to download song from {url}")
        self.url = url


class EffectException(BeatFuncException):
    def __init__(self, failed_effect: Effect) -> None:
        effect_name = "<unknown>"

        if hasattr(failed_effect, "__effect_name__"):
            effect_name = failed_effect.__effect_name__
        elif hasattr(failed_effect, "__name__"):
            effect_name = failed_effect.__name__

        super().__init__(f"Effect with name {effect_name} {repr(failed_effect)} failed to apply")
        self.failed_effect = failed_effect
        self.effect_name = effect_name


class LoadException(BeatFuncException):
    pass


class SongTooLargeException(BeatFuncException):
    def __init__(self, max_size: int) -> None:
        super().__init__(f"Song was too large (max allowed size is {max_size} bytes)")
