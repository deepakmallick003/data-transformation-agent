from flask import Flask, render_template

from app.core.config import get_settings


def create_ui_app() -> Flask:
    settings = get_settings()
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    @app.get("/")
    def index() -> str:
        return render_template("index.html", api_base_url=settings.resolved_backend_url)

    return app
