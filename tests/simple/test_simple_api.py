import json
import shutil
import tempfile
import uuid
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import beatfunc.core

beatfunc.core.config.CACHE_PATH = Path(tempfile.gettempdir())
beatfunc.core.config.DOWNLOAD_PATH = Path(tempfile.gettempdir())

from beatfunc.simple.main import api

client = TestClient(api)


@pytest.fixture(scope="module")
def song_file(request):
    return Path(request.fspath).parent.parent / "drums.mp3"


def test_process_file_basic(song_file):
    resp = client.post(
        "/",
        data={
            # legacy thing: "effects" actually contains a whole job definition, which has another key called "effects"
            "effects": json.dumps({"effects": [{"type": "remove", "period": 2}]}),
        },
        files={"song": song_file.open("rb")},
    )

    assert resp.status_code == HTTPStatus.OK
    assert len(resp.content) > 0


def test_process_url_basic(mocker, song_file):
    def download_song_mock(_):
        mock_file = beatfunc.core.config.DOWNLOAD_PATH / str(uuid.uuid4())
        shutil.copyfile(song_file, mock_file)
        return mock_file

    mocker.patch("beatfunc.core.jobs.download_song", download_song_mock)

    resp = client.post("/yt", json={"url": "https://example.com", "effects": [{"type": "remove", "period": 2}]})

    assert resp.status_code == HTTPStatus.OK
    assert len(resp.content) > 0
