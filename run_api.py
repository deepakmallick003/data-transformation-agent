from app.api.app import create_app
from app.core.config import get_settings

import uvicorn


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
