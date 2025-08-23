from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import get_db_connection

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
        conn.close()
        if user:
            session["user"] = username
            return redirect(url_for("inventory.list_phones"))
        else:
            flash("Invalid username or password", "error")
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("auth.login"))
