from flask import Blueprint, render_template, request, redirect, url_for, session
from database import get_db_connection

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

def login_required(func):
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("auth.login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@inventory_bp.route("/")
@login_required
def list_phones():
    conn = get_db_connection()
    phones = conn.execute("SELECT * FROM phones").fetchall()
    conn.close()
    return render_template("inventory.html", phones=phones)

@inventory_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_phone():
    if request.method == "POST":
        brand = request.form["brand"]
        model = request.form["model"]
        price = request.form["price"]
        condition = request.form["condition"]
        conn = get_db_connection()
        conn.execute("INSERT INTO phones (brand, model, price, condition) VALUES (?, ?, ?, ?)",
                     (brand, model, price, condition))
        conn.commit()
        conn.close()
        return redirect(url_for("inventory.list_phones"))
    return render_template("add_phone.html")

@inventory_bp.route("/edit/<int:phone_id>", methods=["GET", "POST"])
@login_required
def edit_phone(phone_id):
    conn = get_db_connection()
    phone = conn.execute("SELECT * FROM phones WHERE id=?", (phone_id,)).fetchone()
    if request.method == "POST":
        brand = request.form["brand"]
        model = request.form["model"]
        price = request.form["price"]
        condition = request.form["condition"]
        conn.execute("UPDATE phones SET brand=?, model=?, price=?, condition=? WHERE id=?",
                     (brand, model, price, condition, phone_id))
        conn.commit()
        conn.close()
        return redirect(url_for("inventory.list_phones"))
    conn.close()
    return render_template("edit_phone.html", phone=phone)

@inventory_bp.route("/delete/<int:phone_id>")
@login_required
def delete_phone(phone_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM phones WHERE id=?", (phone_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("inventory.list_phones"))
