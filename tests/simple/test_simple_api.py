import json
import fastapi as fa
from pathlib import Path
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from beatfunc.simple.main import api

client = TestClient(api)


@pytest.fixture(scope="module")
def song_file(request):
    return Path(request.fspath).parent.parent / "drums.mp3"


def test_process_file_basic(song_file):
    resp = client.post("/", data={
        # legacy thing: "effects" actually contains a whole job definition, which has another key called "effects"
        "effects": json.dumps({
            "effects": [ {"type": "remove", "period": 2} ]
        }),
    }, files={"song": song_file.open("rb")})

    assert resp.status_code == HTTPStatus.OK
    assert len(resp.content) > 0
