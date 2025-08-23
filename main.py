"""
Refurbished Phone Seller — Flask App with Templates
--------------------------------------------------
Run:
  python main.py
Then open http://127.0.0.1:5000

Default login:
  user: admin
  pass: admin123
"""
from __future__ import annotations
import os, sqlite3
from functools import wraps
from typing import Optional
from flask import (
    Flask, request, redirect, url_for, render_template,
    session, flash
)

# ---------------- Configuration ----------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
DB_PATH = os.getenv("DB_PATH", "phones.db")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ALLOWED_CONDITIONS = {"New", "Good", "Scrap"}

# ---------------- Helpers ----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS phones(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT NOT NULL,
        model TEXT NOT NULL,
        price REAL NOT NULL,
        condition TEXT NOT NULL,
        description TEXT DEFAULT ''
    )
    """)
    conn.commit()
    conn.close()
    print("Database ready.")

def login_required(fn):
    @wraps(fn)
    def wrap(*a,**k):
        if not session.get("user"):
            flash("Please log in.","warning")
            return redirect(url_for("login", next=request.path))
        return fn(*a,**k)
    return wrap

def sanitize(s:Optional[str])->str:
    return " ".join((s or "").strip().split())[:200]

# ---------------- Routes ----------------
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=sanitize(request.form.get("username"))
        p=request.form.get("password","")
        if u==ADMIN_USER and p==ADMIN_PASSWORD:
            session["user"]=u
            flash("Logged in.","success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid credentials.","danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out.","info")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    conn=get_db()
    rows=conn.execute("SELECT * FROM phones ORDER BY brand, model").fetchall()
    conn.close()
    return render_template("dashboard.html", rows=rows, conditions=ALLOWED_CONDITIONS)

@app.route("/add", methods=["GET","POST"])
@login_required
def add_phone():
    if request.method=="POST":
        brand=sanitize(request.form.get("brand"))
        model=sanitize(request.form.get("model"))
        price=request.form.get("price")
        condition=sanitize(request.form.get("condition"))
        description=request.form.get("description","")
        if not brand or not model or not price or not condition:
            flash("All fields except description are required.","error")
            return redirect(url_for("add_phone"))
        conn=get_db()
        conn.execute("INSERT INTO phones(brand,model,price,condition,description) VALUES(?,?,?,?,?)",
                     (brand,model,float(price),condition,description))
        conn.commit(); conn.close()
        flash("Phone added.","success")
        return redirect(url_for("dashboard"))
    return render_template("form.html", action="Add", phone=None, conditions=ALLOWED_CONDITIONS)

@app.route("/edit/<int:id>", methods=["GET","POST"])
@login_required
def edit_phone(id):
    conn=get_db()
    phone=conn.execute("SELECT * FROM phones WHERE id=?",(id,)).fetchone()
    if phone is None:
        conn.close(); flash("Phone not found.","error"); return redirect(url_for("dashboard"))
    if request.method=="POST":
        brand=sanitize(request.form.get("brand"))
        model=sanitize(request.form.get("model"))
        price=request.form.get("price")
        condition=sanitize(request.form.get("condition"))
        description=request.form.get("description","")
        if not brand or not model or not price or not condition:
            flash("All fields except description are required.","error")
            return redirect(url_for("edit_phone",id=id))
        conn.execute("UPDATE phones SET brand=?,model=?,price=?,condition=?,description=? WHERE id=?",
                     (brand,model,float(price),condition,description,id))
        conn.commit(); conn.close()
        flash("Phone updated.","success")
        return redirect(url_for("dashboard"))
    conn.close()
    return render_template("form.html", action="Edit", phone=phone, conditions=ALLOWED_CONDITIONS)

@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_phone(id):
    conn=get_db()
    conn.execute("DELETE FROM phones WHERE id=?",(id,))
    conn.commit(); conn.close()
    flash("Phone deleted.","success")
    return redirect(url_for("dashboard"))

# ---------------- Main ----------------
if __name__=="__main__":
    init_db()
    app.run(debug=True)
