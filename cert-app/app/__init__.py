import os

from flask import Flask, g, jsonify, redirect

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder=FRONTEND_DIR,
        static_url_path="",
    )
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        EMAIL_ENCRYPTION_KEY=os.environ.get("EMAIL_ENCRYPTION_KEY"),
        SESSION_COOKIE_SAMESITE="Lax",
        DATABASE=os.environ.get(
            "DATABASE_PATH", os.path.join(app.instance_path, "certificates.db")
        ),
    )
    if test_config:
        app.config.update(test_config)

    from . import db

    db.init_app(app)

    from .auth import auth_bp
    from .email_settings import email_bp
    from .routes import bp
    from .bulk import bulk_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(bulk_bp)

    # Pages. The app needs a login; the login and sign-up pages don't.
    @app.get("/")
    def index():
        if g.user is None:
            return redirect("/login")
        return app.send_static_file("index.html")

    @app.get("/login")
    def login_page():
        if g.user is not None:
            return redirect("/")
        return app.send_static_file("login.html")

    @app.get("/signup")
    def signup_page():
        if g.user is not None:
            return redirect("/")
        return app.send_static_file("signup.html")

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": {"code": "NOT_FOUND", "message": "Resource not found"}}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return (
            jsonify({"error": {"code": "METHOD_NOT_ALLOWED", "message": "Method not allowed"}}),
            405,
        )

    @app.errorhandler(500)
    def server_error(_e):
        return (
            jsonify({"error": {"code": "SERVER_ERROR", "message": "Something went wrong"}}),
            500,
        )

    return app
