from flask import Flask, redirect, url_for
from database import init_db
from auth import auth_bp
from inventory import inventory_bp

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(inventory_bp)

@app.before_request
def before_request():
    init_db()

@app.route("/")
def home():
    return redirect(url_for("inventory.list_phones"))

if __name__ == "__main__":
    app.run(debug=True)
