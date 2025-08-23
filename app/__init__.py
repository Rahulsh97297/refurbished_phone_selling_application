# app/__init__.py
from flask import Flask, render_template
from dotenv import load_dotenv
from .extensions import db
from .routes.phones import bp as phones_bp
from .routes.search import bp as search_bp
from .routes.platforms import bp as platforms_bp

def create_app():
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True, template_folder="templates")
    app.config.from_object("config.Config")

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Blueprints
    app.register_blueprint(phones_bp, url_prefix="/phones")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(platforms_bp, url_prefix="/platforms")

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
