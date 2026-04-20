from flask import Flask, make_response, redirect, render_template, request, url_for

from app.core.auth import AUTH_COOKIE_NAME, clear_auth_cookie, is_authenticated_cookie, set_auth_cookie
from app.core.config import get_settings


def create_ui_app() -> Flask:
    settings = get_settings()
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    @app.before_request
    def require_login() -> str | None:
        if request.path.startswith("/static/") or request.path == "/login":
            return None
        if is_authenticated_cookie(request.cookies.get(AUTH_COOKIE_NAME), settings):
            return None
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login() -> str:
        if is_authenticated_cookie(request.cookies.get(AUTH_COOKIE_NAME), settings):
            return redirect(url_for("index"))

        error = None
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if username == settings.auth_username and password == settings.auth_password:
                response = make_response(redirect(url_for("index")))
                set_auth_cookie(response, settings)
                return response
            error = "Incorrect username or password."

        return render_template("login.html", error=error)

    @app.post("/logout")
    def logout() -> str:
        response = make_response(redirect(url_for("login")))
        clear_auth_cookie(response)
        return response

    @app.get("/")
    def index() -> str:
        return render_template("index.html", api_base_url=settings.resolved_backend_url)

    return app
