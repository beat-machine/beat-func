import os
from pathlib import Path


def conf_namespace(namespace: str):
    def factory(name: str):
        return f"BF__{namespace.upper()}__{name.upper()}"

    return factory


_ns = conf_namespace("core")

MD5_BLOCK_SIZE = 512
MAX_FILE_SIZE = int(os.getenv(_ns("max_file_size"), 12000000))
CACHE_PATH = Path(os.getenv(_ns("cache_path"), "cache"))
DOWNLOAD_PATH = Path(os.getenv(_ns("download_path"), "download"))

CACHE_PATH.mkdir(parents=True, exist_ok=True)
DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)

del _ns
