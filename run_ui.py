from app.core.config import get_settings
from app.web.app import create_ui_app


app = create_ui_app()


if __name__ == "__main__":
    settings = get_settings()
    app.run(host=settings.ui_host, port=settings.ui_port, debug=False)
