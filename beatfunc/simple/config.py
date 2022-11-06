import os

from .. import core

_ns = core.config.conf_namespace('cloud_run')

ORIGINS = (os.getenv('origins', '*')).split(';')
ALLOW_URLS = bool(int(os.getenv('allow_yt', '1')))

del _ns
