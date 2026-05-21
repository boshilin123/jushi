from flask import Flask

from modules.ports import ports_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(ports_bp, url_prefix="/api/port-list")
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8091, debug=True)
