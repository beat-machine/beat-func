import http
import io
import json
import os
import tempfile

import beatmachine as bm
import flask


def process_song(request: flask.Request):
    try:
        effect_data = json.loads(request.form['effects'])
        effects = [bm.effects.load_from_dict(e) for e in effect_data]
    except KeyError:
        return 'Missing effects', http.HTTPStatus.BAD_REQUEST
    except ValueError:
        return 'Invalid effects', http.HTTPStatus.BAD_REQUEST

    if len(effects) > 10:
        return 'Too many effects (max is 10)', http.HTTPStatus.BAD_REQUEST

    try:
        song_file = request.files['song']
    except KeyError:
        return 'Missing song', http.HTTPStatus.BAD_REQUEST

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as fp:
        song_file.save(fp)
        filename = fp.name

    beats = bm.loader.load_beats_by_signal(filename)
    edited_beats = bm.editor.apply_effects(beats, effects)

    buf = io.BytesIO()
    sum(list(edited_beats)).export(buf, format='mp3')
    buf.seek(0)

    os.remove(filename)

    return flask.send_file(buf, mimetype='audio/mpeg')
