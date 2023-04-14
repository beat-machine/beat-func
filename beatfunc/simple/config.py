import os

from .. import core

_ns = core.config.conf_namespace("cloud_run")

ORIGINS = (os.getenv(_ns("origins"), "*")).split(";")
ALLOW_URLS = bool(int(os.getenv(_ns("allow_urls"), "1")))

del _ns
