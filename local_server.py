import flask

from main import process_song

if __name__ == "__main__":
    app = flask.Flask(__name__)

    @app.route('/', methods=['POST'])
    def index():
        return process_song(flask.request)

    app.run('127.0.0.1', 8000, debug=True)
