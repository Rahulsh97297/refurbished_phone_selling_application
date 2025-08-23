# # app/__init__.py
# from flask import Flask, redirect, url_for
# from dotenv import load_dotenv
# from .extensions import db
# from .routes.phones import bp as phones_bp
# from .routes.search import bp as search_bp
# from .routes.platforms import bp as platforms_bp

# def create_app():
#     load_dotenv()
#     app = Flask(__name__, instance_relative_config=True, template_folder="templates", static_folder="static", static_url_path="/static")
#     app.config.from_object("config.Config")
#     app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # Disable caching for development
#     app.config["TEMPLATES_AUTO_RELOAD"] = True
#     db.init_app(app)

#     with app.app_context():
#         db.create_all()

#     # Blueprints
#     app.register_blueprint(phones_bp, url_prefix="/phones")
#     app.register_blueprint(search_bp, url_prefix="/search")
#     app.register_blueprint(platforms_bp, url_prefix="/platforms")

#     @app.get("/")
#     def index():
#         # FIX: avoid rendering template without 'phones' context; send user to list page
#         return redirect(url_for("phones.list_phones_ui"))

#     return app
# app/__init__.py
from flask import Flask, redirect, url_for
from dotenv import load_dotenv
from .extensions import db
from .routes.phones import bp as phones_bp
from .routes.search import bp as search_bp
from .routes.platforms import bp as platforms_bp
import time

def create_app():
    load_dotenv()
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
    )
    app.config.from_object("config.Config")

    # Ensure changes show up immediately in dev
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Expose a version token to bust caches in templates
    @app.context_processor
    def inject_asset_version():
        return {"asset_v": int(time.time())}

    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(phones_bp, url_prefix="/phones")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(platforms_bp, url_prefix="/platforms")

    @app.get("/")
    def index():
        return redirect(url_for("phones.list_phones_ui"))

    return app
