import http
import io
import json
from tempfile import NamedTemporaryFile

import beatmachine as bm
from fastapi import FastAPI, Form, File
from starlette.responses import StreamingResponse

app = FastAPI()


@app.post('/')
async def process_song(
        effects: str = Form(default=None),
        song: bytes = File(default=None),
):
    try:
        effect_data = json.loads(effects)
        effects = [bm.effects.load_from_dict(e) for e in effect_data]
    except KeyError:
        return 'Missing effects', http.HTTPStatus.BAD_REQUEST
    except ValueError:
        return 'Invalid effects', http.HTTPStatus.BAD_REQUEST

    if len(effects) > 10:
        return 'Too many effects (max is 10)', http.HTTPStatus.BAD_REQUEST

    with NamedTemporaryFile(suffix='.mp3', delete=False) as fp:
        fp.write(song)
        filename = fp.name

    beats = bm.loader.load_beats_by_signal(filename)
    edited_beats = bm.editor.apply_effects(beats, effects)

    buf = io.BytesIO()
    sum(list(edited_beats)).export(buf, format='mp3')
    buf.seek(0)

    return StreamingResponse(buf, media_type='audio/mpeg')
