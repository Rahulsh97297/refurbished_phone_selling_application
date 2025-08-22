"""
Refurbished Phone Seller — Flask Demo (Single File)
--------------------------------------------------
A self‑contained Flask app that manages inventory and mock‑lists refurbished
phones to three dummy platforms (X, Y, Z) with platform‑specific fees and
condition mappings.

Key features implemented:
- Admin login (mock auth) and logout
- Add / Update / Delete phones
- Stock management (+ prevent listing when out of stock or B2B/direct reserved)
- Bulk CSV upload for inventory
- Automatic platform price calculation (+ optional manual overrides)
- Profitability check to avoid unprofitable listings (uses cost_price)
- Dummy platform listing with per‑platform condition mapping & errors
- Search (brand/model) and filters (condition, listed on platform)
- Simple, responsive UI with Bootstrap
- Basic input validation/sanitization, parameterized SQL (sqlite3)

Run locally:
  python app.py
Then open: http://127.0.0.1:5000

Default admin credentials:
  user: admin
  pass: admin123  (Change via ADMIN_PASSWORD env var)

CSV bulk upload format (header row required):
brand,model,storage,color,condition,base_price,cost_price,stock,tags
Apple,iPhone 12,128GB,Black,Good,350,280,5,
Samsung,Galaxy S21,256GB,Violet,New,450,360,3,reserved_b2b

Note: Base price is the target *net* you want to receive after platform fees.
Listing prices are auto-computed so you net the base price after fees.

Security notes (mock):
- Session cookie auth with a single admin user (demo only).
- Input validation and server-side checks included, but this is NOT production hardening.

"""
from __future__ import annotations
import csv
import os
import sqlite3
from dataclasses import dataclass
from functools import wraps
from typing import Dict, Optional, Tuple

from flask import (
    Flask, request, redirect, url_for, render_template_string, session,
    flash, send_file
)

# -----------------------------
# Configuration
# -----------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
DB_PATH = os.getenv("DB_PATH", "phones.db")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

ALLOWED_CONDITIONS = {"New", "Good", "Scrap"}
PLATFORMS = ["X", "Y", "Z"]

# Fee definitions (as functions mapping base_net -> list_price)
# Base price is the desired NET after fees.

def calc_price_X(base_net: float) -> float:
    # X: 10% fee -> net = price * (1 - 0.10)
    return round(base_net / 0.90, 2)

def calc_price_Y(base_net: float) -> float:
    # Y: 8% fee + $2 flat -> net = price * 0.92 - 2
    # => price = (base_net + 2) / 0.92
    return round((base_net + 2.0) / 0.92, 2)

def calc_price_Z(base_net: float) -> float:
    # Z: 12% fee -> net = price * 0.88
    return round(base_net / 0.88, 2)

CALCULATORS = {
    "X": calc_price_X,
    "Y": calc_price_Y,
    "Z": calc_price_Z,
}

# Condition mappings per platform
COND_MAP = {
    "X": {
        "New": "New",
        "Good": "Good",
        "Scrap": "Scrap",
    },
    "Y": {
        "New": "3 stars (Excellent)",
        "Good": "2 stars (Good)",
        "Scrap": "1 star (Usable)",
    },
    "Z": {
        "New": "New",
        "Good": "Good",
        # We'll map "Scrap" to the closest supported or reject it
        # Z supports: New, As New, Good
        # We'll *reject* Scrap on Z to demonstrate platform-specific error.
    },
}

# -----------------------------
# Helpers
# -----------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            storage TEXT,
            color TEXT,
            condition TEXT NOT NULL,
            base_price REAL NOT NULL CHECK(base_price >= 0),
            cost_price REAL NOT NULL DEFAULT 0 CHECK(cost_price >= 0),
            stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
            tags TEXT DEFAULT "",
            # computed platform prices
            price_x REAL,
            price_y REAL,
            price_z REAL,
            override_x INTEGER DEFAULT 0,
            override_y INTEGER DEFAULT 0,
            override_z INTEGER DEFAULT 0,
            # listing status
            status_x TEXT DEFAULT "unlisted", -- unlisted | listed | failed
            message_x TEXT DEFAULT "",
            status_y TEXT DEFAULT "unlisted",
            message_y TEXT DEFAULT "",
            status_z TEXT DEFAULT "unlisted",
            message_z TEXT DEFAULT ""
        )
        """
    )
    conn.commit()
    conn.close()


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapper


# Basic validators

def sanitize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    # Trim, collapse whitespace, limit length
    s = " ".join(s.strip().split())
    return s[:200]


def parse_float(name: str, value: str, minimum: float = 0.0) -> Tuple[Optional[float], Optional[str]]:
    try:
        f = float(value)
        if f < minimum:
            return None, f"{name} must be ≥ {minimum}."
        return f, None
    except Exception:
        return None, f"{name} must be a number."


def parse_int(name: str, value: str, minimum: int = 0) -> Tuple[Optional[int], Optional[str]]:
    try:
        i = int(value)
        if i < minimum:
            return None, f"{name} must be ≥ {minimum}."
        return i, None
    except Exception:
        return None, f"{name} must be an integer."


def auto_prices(base_price: float) -> Dict[str, float]:
    return {p: CALCULATORS[p](base_price) for p in PLATFORMS}


def profitable(base_net: float, cost_price: float) -> bool:
    return base_net > cost_price


def stock_available(stock: int, tags: str) -> bool:
    t = (tags or "").lower()
    if stock <= 0:
        return False
    # If B2B or direct reserved flags
    if "reserved_b2b" in t or "reserved_direct" in t or "out_of_stock" in t:
        return False
    return True


def platform_condition(platform: str, condition: str) -> Tuple[bool, str]:
    mapping = COND_MAP.get(platform, {})
    if condition in mapping:
        return True, mapping[condition]
    return False, f"Condition '{condition}' not supported on {platform}."


# -----------------------------
# Routes
# -----------------------------
@app.before_first_request
def setup():
    init_db()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = sanitize_text(request.form.get("username"))
        pw = request.form.get("password", "")
        if user == ADMIN_USER and pw == ADMIN_PASSWORD:
            session["user"] = user
            flash("Logged in successfully.", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template_string(TPL_LOGIN)


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    q = sanitize_text(request.args.get("q"))
    cond = sanitize_text(request.args.get("condition"))
    listed = sanitize_text(request.args.get("listed"))  # X | Y | Z | any | unlisted

    sql = "SELECT * FROM phones WHERE 1=1"
    params = []
    if q:
        sql += " AND (LOWER(brand) LIKE ? OR LOWER(model) LIKE ?)"
        like = f"%{q.lower()}%"
        params += [like, like]
    if cond:
        sql += " AND condition = ?"
        params.append(cond)
    if listed:
        if listed in PLATFORMS:
            sql += f" AND status_{listed.lower()} = 'listed'"
        elif listed == "any":
            sql += " AND (status_x='listed' OR status_y='listed' OR status_z='listed')"
        elif listed == "unlisted":
            sql += " AND (status_x='unlisted' AND status_y='unlisted' AND status_z='unlisted')"

    sql += " ORDER BY brand, model"

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return render_template_string(TPL_DASH, rows=rows, q=q, cond=cond, listed=listed,
                                  ALLOWED_CONDITIONS=ALLOWED_CONDITIONS)


@app.route("/phone/new", methods=["GET", "POST"])
@login_required
def phone_new():
    if request.method == "POST":
        return save_phone()
    return render_template_string(TPL_FORM, phone=None)


@app.route("/phone/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def phone_edit(pid: int):
    conn = get_db()
    phone = conn.execute("SELECT * FROM phones WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not phone:
        flash("Phone not found.", "warning")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        return save_phone(pid)
    return render_template_string(TPL_FORM, phone=phone)


@app.route("/phone/<int:pid>/delete", methods=["POST"])
@login_required
def phone_delete(pid: int):
    conn = get_db()
    conn.execute("DELETE FROM phones WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Deleted phone.", "info")
    return redirect(url_for("dashboard"))


@app.route("/bulk_upload", methods=["GET", "POST"])
@login_required
def bulk_upload():
    if request.method == "POST":
        file = request.files.get("file")
        if not file or not file.filename.lower().endswith(".csv"):
            flash("Please upload a CSV file.", "warning")
            return redirect(url_for("bulk_upload"))
        added = 0
        updated = 0
        conn = get_db()
        reader = csv.DictReader((line.decode("utf-8", errors="ignore") for line in file.stream))
        for row in reader:
            brand = sanitize_text(row.get("brand"))
            model = sanitize_text(row.get("model"))
            if not brand or not model:
                continue
            storage = sanitize_text(row.get("storage"))
            color = sanitize_text(row.get("color"))
            condition = sanitize_text(row.get("condition")) or "Good"
            if condition not in ALLOWED_CONDITIONS:
                condition = "Good"
            base_price = float(row.get("base_price") or 0)
            cost_price = float(row.get("cost_price") or 0)
            stock = int(float(row.get("stock") or 0))
            tags = sanitize_text(row.get("tags"))
            prices = auto_prices(base_price)

            # Upsert by (brand, model, storage, color)
            existing = conn.execute(
                "SELECT id FROM phones WHERE brand=? AND model=? AND IFNULL(storage,'')=IFNULL(?, '') AND IFNULL(color,'')=IFNULL(?, '')",
                (brand, model, storage, color)
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE phones SET condition=?, base_price=?, cost_price=?, stock=?, tags=?,
                        price_x=?, price_y=?, price_z=?
                    WHERE id=?
                    """,
                    (condition, base_price, cost_price, stock, tags,
                     prices["X"], prices["Y"], prices["Z"], existing["id"])
                )
                updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO phones(brand, model, storage, color, condition, base_price, cost_price, stock, tags,
                        price_x, price_y, price_z)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (brand, model, storage, color, condition, base_price, cost_price, stock, tags,
                     prices["X"], prices["Y"], prices["Z"])
                )
                added += 1
        conn.commit()
        conn.close()
        flash(f"Bulk upload complete. Added {added}, Updated {updated}.", "success")
        return redirect(url_for("dashboard"))
    return render_template_string(TPL_BULK)


@app.route("/auto_update_prices", methods=["POST"])
@login_required
def auto_update_prices():
    conn = get_db()
    phones = conn.execute("SELECT * FROM phones").fetchall()
    for p in phones:
        prices = auto_prices(p["base_price"])
        # Only update if not manually overridden
        if not p["override_x"]:
            conn.execute("UPDATE phones SET price_x=? WHERE id=?", (prices["X"], p["id"]))
        if not p["override_y"]:
            conn.execute("UPDATE phones SET price_y=? WHERE id=?", (prices["Y"], p["id"]))
        if not p["override_z"]:
            conn.execute("UPDATE phones SET price_z=? WHERE id=?", (prices["Z"], p["id"]))
    conn.commit()
    conn.close()
    flash("Automated prices updated from base net price.", "success")
    return redirect(url_for("dashboard"))


@app.route("/list/<int:pid>/<platform>", methods=["POST"])
@login_required
def list_platform(pid: int, platform: str):
    platform = platform.upper()
    if platform not in PLATFORMS:
        flash("Unknown platform.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_db()
    p = conn.execute("SELECT * FROM phones WHERE id=?", (pid,)).fetchone()
    if not p:
        flash("Phone not found.", "warning")
        return redirect(url_for("dashboard"))

    # Checks: stock & tags
    if not stock_available(p["stock"], p["tags"]):
        msg = "Out of stock or reserved for B2B/direct sales."
        conn.execute(f"UPDATE phones SET status_{platform.lower()}=?, message_{platform.lower()}=? WHERE id=?",
                     ("failed", msg, pid))
        conn.commit()
        conn.close()
        flash(f"Listing failed on {platform}: {msg}", "warning")
        return redirect(url_for("dashboard"))

    # Profitability
    if not profitable(p["base_price"], p["cost_price"]):
        msg = "Unprofitable: base net ≤ cost price."
        conn.execute(f"UPDATE phones SET status_{platform.lower()}=?, message_{platform.lower()}=? WHERE id=?",
                     ("failed", msg, pid))
        conn.commit()
        conn.close()
        flash(f"Listing failed on {platform}: {msg}", "warning")
        return redirect(url_for("dashboard"))

    # Condition mapping
    ok, mapped = platform_condition(platform, p["condition"])
    if not ok:
        msg = mapped
        conn.execute(f"UPDATE phones SET status_{platform.lower()}=?, message_{platform.lower()}=? WHERE id=?",
                     ("failed", msg, pid))
        conn.commit()
        conn.close()
        flash(f"Listing failed on {platform}: {msg}", "warning")
        return redirect(url_for("dashboard"))

    # Simulate API listing success
    price_field = f"price_{platform.lower()}"
    list_price = p[price_field]
    msg = f"Listed as '{mapped}' at ${list_price}."
    conn.execute(f"UPDATE phones SET status_{platform.lower()}=?, message_{platform.lower()}=? WHERE id=?",
                 ("listed", msg, pid))
    conn.commit()
    conn.close()
    flash(f"Success on {platform}: {msg}", "success")
    return redirect(url_for("dashboard"))


def save_phone(pid: Optional[int] = None):
    # Gather & validate
    brand = sanitize_text(request.form.get("brand"))
    model = sanitize_text(request.form.get("model"))
    storage = sanitize_text(request.form.get("storage"))
    color = sanitize_text(request.form.get("color"))
    condition = sanitize_text(request.form.get("condition"))

    if condition not in ALLOWED_CONDITIONS:
        flash("Invalid condition.", "danger")
        return redirect(request.referrer or url_for("dashboard"))

    base_price, err = parse_float("Base price", request.form.get("base_price", ""), 0)
    if err:
        flash(err, "danger")
        return redirect(request.referrer or url_for("dashboard"))
    cost_price, err2 = parse_float("Cost price", request.form.get("cost_price", "0"), 0)
    if err2:
        flash(err2, "danger")
        return redirect(request.referrer or url_for("dashboard"))
    stock, err3 = parse_int("Stock", request.form.get("stock", "0"), 0)
    if err3:
        flash(err3, "danger")
        return redirect(request.referrer or url_for("dashboard"))

    tags = sanitize_text(request.form.get("tags"))

    # Overrides
    override_x = 1 if request.form.get("override_x") == "on" else 0
    override_y = 1 if request.form.get("override_y") == "on" else 0
    override_z = 1 if request.form.get("override_z") == "on" else 0

    # If override, parse manual prices; else auto compute
    prices = auto_prices(base_price)
    def get_manual(name, default):
        val = request.form.get(name, "").strip()
        if not val:
            return default
        try:
            f = float(val)
            return round(max(f, 0.0), 2)
        except Exception:
            return default

    price_x = get_manual("price_x", prices["X"]) if override_x else prices["X"]
    price_y = get_manual("price_y", prices["Y"]) if override_y else prices["Y"]
    price_z = get_manual("price_z", prices["Z"]) if override_z else prices["Z"]

    if not brand or not model:
        flash("Brand and Model are required.", "danger")
        return redirect(request.referrer or url_for("dashboard"))

    conn = get_db()
    if pid:
        conn.execute(
            """
            UPDATE phones SET brand=?, model=?, storage=?, color=?, condition=?,
                base_price=?, cost_price=?, stock=?, tags=?,
                price_x=?, price_y=?, price_z=?,
                override_x=?, override_y=?, override_z=?
            WHERE id=?
            """,
            (brand, model, storage, color, condition, base_price, cost_price, stock, tags,
             price_x, price_y, price_z,
             override_x, override_y, override_z, pid)
        )
        conn.commit()
        conn.close()
        flash("Phone updated.", "success")
    else:
        conn.execute(
            """
            INSERT INTO phones(brand, model, storage, color, condition, base_price, cost_price, stock, tags,
                price_x, price_y, price_z, override_x, override_y, override_z)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (brand, model, storage, color, condition, base_price, cost_price, stock, tags,
             price_x, price_y, price_z, override_x, override_y, override_z)
        )
        conn.commit()
        conn.close()
        flash("Phone added.", "success")
    return redirect(url_for("dashboard"))


# -----------------------------
# Templates (Jinja2 via render_template_string)
# -----------------------------
TPL_BASE = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Refurbished Phone Seller</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    .badge-tag { background-color: #eef; color: #334; margin-right: 4px; }
    .table thead th { white-space: nowrap; }
    .sticky-top { top: 0.5rem; }
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg bg-body-tertiary border-bottom">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('dashboard') }}">📱 Refurbished Seller</a>
    <div class="d-flex">
      <a class="btn btn-outline-secondary me-2" href="{{ url_for('bulk_upload') }}">Bulk Upload</a>
      <form method="post" action="{{ url_for('auto_update_prices') }}">
        <button class="btn btn-outline-primary me-2" type="submit">Auto Update Prices</button>
      </form>
      <a class="btn btn-danger" href="{{ url_for('logout') }}">Logout</a>
    </div>
  </div>
</nav>
<div class="container py-4">
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, message in messages %}
        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
          {{ message }}
          <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
      {% endfor %}
    {% endif %}
  {% endwith %}
  {% block content %}{% endblock %}
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

TPL_LOGIN = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login — Refurbished Seller</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light d-flex align-items-center" style="min-height: 100vh;">
  <div class="container">
    <div class="row justify-content-center">
      <div class="col-md-4">
        <div class="card shadow-sm">
          <div class="card-body">
            <h5 class="card-title mb-3">Admin Login</h5>
            <form method="post">
              <div class="mb-3">
                <label class="form-label">Username</label>
                <input name="username" class="form-control" required>
              </div>
              <div class="mb-3">
                <label class="form-label">Password</label>
                <input type="password" name="password" class="form-control" required>
              </div>
              <button class="btn btn-primary w-100">Login</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

TPL_DASH = r"""
{% extends TPL_BASE %}
{% block content %}
<div class="row g-4">
  <div class="col-lg-3">
    <div class="card shadow-sm sticky-top">
      <div class="card-body">
        <h5 class="mb-3">Filters</h5>
        <form method="get" action="{{ url_for('dashboard') }}">
          <div class="mb-2">
            <label class="form-label">Search (brand/model)</label>
            <input name="q" value="{{ q }}" class="form-control" placeholder="e.g. iPhone, Samsung">
          </div>
          <div class="mb-2">
            <label class="form-label">Condition</label>
            <select class="form-select" name="condition">
              <option value="">Any</option>
              {% for c in sorted(ALLOWED_CONDITIONS) %}
              <option value="{{ c }}" {% if cond==c %}selected{% endif %}>{{ c }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Listed on</label>
            <select class="form-select" name="listed">
              <option value="">Any status</option>
              <option value="X" {% if listed=='X' %}selected{% endif %}>Platform X</option>
              <option value="Y" {% if listed=='Y' %}selected{% endif %}>Platform Y</option>
              <option value="Z" {% if listed=='Z' %}selected{% endif %}>Platform Z</option>
              <option value="any" {% if listed=='any' %}selected{% endif %}>Listed on any</option>
              <option value="unlisted" {% if listed=='unlisted' %}selected{% endif %}>Not listed anywhere</option>
            </select>
          </div>
          <div class="d-grid gap-2">
            <button class="btn btn-primary" type="submit">Apply</button>
            <a class="btn btn-outline-secondary" href="{{ url_for('dashboard') }}">Reset</a>
          </div>
        </form>
      </div>
    </div>
  </div>
  <div class="col-lg-9">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Inventory</h4>
      <a href="{{ url_for('phone_new') }}" class="btn btn-success">+ Add Phone</a>
    </div>
    <div class="table-responsive">
      <table class="table table-sm align-middle table-striped">
        <thead>
          <tr>
            <th>Brand</th><th>Model</th><th>Specs</th><th>Cond</th><th>Stock</th>
            <th>Cost</th><th>Base (net)</th>
            <th>X Price</th><th>Y Price</th><th>Z Price</th>
            <th>Listing</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {% for p in rows %}
          <tr>
            <td>{{ p.brand }}</td>
            <td>{{ p.model }}</td>
            <td>{{ (p.storage or '') ~ (' / ' ~ p.color if p.color else '') }}</td>
            <td>{{ p.condition }}</td>
            <td>{{ p.stock }}</td>
            <td>${{ '%.2f'|format(p.cost_price or 0) }}</td>
            <td>${{ '%.2f'|format(p.base_price) }}</td>
            <td>${{ '%.2f'|format(p.price_x or 0) }} {% if p.override_x %}<span class="badge text-bg-warning">manual</span>{% endif %}</td>
            <td>${{ '%.2f'|format(p.price_y or 0) }} {% if p.override_y %}<span class="badge text-bg-warning">manual</span>{% endif %}</td>
            <td>${{ '%.2f'|format(p.price_z or 0) }} {% if p.override_z %}<span class="badge text-bg-warning">manual</span>{% endif %}</td>
            <td style="min-width:240px;">
              {% for plat in ['X','Y','Z'] %}
                {% set st = attribute(p, 'status_' + plat.lower()) %}
                {% set msg = attribute(p, 'message_' + plat.lower()) %}
                <div class="mb-1">
                  <span class="badge {% if st=='listed' %}text-bg-success{% elif st=='failed' %}text-bg-danger{% else %}text-bg-secondary{% endif %}">{{ plat }}: {{ st }}</span>
                  {% if msg %}<small class="text-muted">— {{ msg }}</small>{% endif %}
                </div>
              {% endfor %}
            </td>
            <td>
              <div class="btn-group btn-group-sm" role="group">
                <a class="btn btn-outline-primary" href="{{ url_for('phone_edit', pid=p.id) }}">Edit</a>
                <form method="post" action="{{ url_for('phone_delete', pid=p.id) }}" onsubmit="return confirm('Delete this phone?');">
                  <button class="btn btn-outline-danger">Delete</button>
                </form>
              </div>
              <div class="mt-2 d-flex gap-1">
                <form method="post" action="{{ url_for('list_platform', pid=p.id, platform='X') }}">
                  <button class="btn btn-sm btn-success">List on X</button>
                </form>
                <form method="post" action="{{ url_for('list_platform', pid=p.id, platform='Y') }}">
                  <button class="btn btn-sm btn-success">List on Y</button>
                </form>
                <form method="post" action="{{ url_for('list_platform', pid=p.id, platform='Z') }}">
                  <button class="btn btn-sm btn-success">List on Z</button>
                </form>
              </div>
            </td>
          </tr>
          {% else %}
          <tr><td colspan="12" class="text-center text-muted">No phones found.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}
"""

TPL_FORM = r"""
{% extends TPL_BASE %}
{% block content %}
<h4>{{ 'Edit Phone' if phone else 'Add Phone' }}</h4>
<form method="post" class="row g-3">
  <div class="col-md-3">
    <label class="form-label">Brand*</label>
    <input name="brand" value="{{ phone.brand if phone else '' }}" class="form-control" required>
  </div>
  <div class="col-md-3">
    <label class="form-label">Model*</label>
    <input name="model" value="{{ phone.model if phone else '' }}" class="form-control" required>
  </div>
  <div class="col-md-2">
    <label class="form-label">Storage</label>
    <input name="storage" value="{{ phone.storage if phone else '' }}" class="form-control" placeholder="e.g. 128GB">
  </div>
  <div class="col-md-2">
    <label class="form-label">Color</label>
    <input name="color" value="{{ phone.color if phone else '' }}" class="form-control">
  </div>
  <div class="col-md-2">
    <label class="form-label">Condition*</label>
    <select name="condition" class="form-select" required>
      {% for c in sorted(ALLOWED_CONDITIONS) %}
        <option value="{{ c }}" {% if phone and phone.condition==c %}selected{% endif %}>{{ c }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-md-2">
    <label class="form-label">Cost Price</label>
    <input type="number" step="0.01" min="0" name="cost_price" value="{{ '%.2f'|format(phone.cost_price) if phone else '0.00' }}" class="form-control">
    <div class="form-text">Used for profitability check</div>
  </div>
  <div class="col-md-2">
    <label class="form-label">Base Price (Net)*</label>
    <input type="number" step="0.01" min="0" name="base_price" value="{{ '%.2f'|format(phone.base_price) if phone else '' }}" class="form-control" required>
    <div class="form-text">Net you want after fees</div>
  </div>
  <div class="col-md-2">
    <label class="form-label">Stock*</label>
    <input type="number" step="1" min="0" name="stock" value="{{ phone.stock if phone else 0 }}" class="form-control" required>
  </div>
  <div class="col-md-6">
    <label class="form-label">Tags</label>
    <input name="tags" value="{{ phone.tags if phone else '' }}" class="form-control" placeholder="e.g. reserved_b2b, discontinued">
  </div>

  <div class="col-12"><hr></div>
  <div class="col-12"><strong>Platform Prices</strong> <span class="text-muted">(auto from Base Net; tick override to set manual)</span></div>
  <div class="col-md-4">
    <div class="form-check form-switch">
      <input class="form-check-input" type="checkbox" id="ovx" name="override_x" {% if phone and phone.override_x %}checked{% endif %}>
      <label class="form-check-label" for="ovx">Override X</label>
    </div>
    <label class="form-label">Price for X</label>
    <input name="price_x" type="number" step="0.01" min="0" class="form-control" value="{{ '%.2f'|format(phone.price_x) if phone else '' }}">
  </div>
  <div class="col-md-4">
    <div class="form-check form-switch">
      <input class="form-check-input" type="checkbox" id="ovy" name="override_y" {% if phone and phone.override_y %}checked{% endif %}>
      <label class="form-check-label" for="ovy">Override Y</label>
    </div>
    <label class="form-label">Price for Y</label>
    <input name="price_y" type="number" step="0.01" min="0" class="form-control" value="{{ '%.2f'|format(phone.price_y) if phone else '' }}">
  </div>
  <div class="col-md-4">
    <div class="form-check form-switch">
      <input class="form-check-input" type="checkbox" id="ovz" name="override_z" {% if phone and phone.override_z %}checked{% endif %}>
      <label class="form-check-label" for="ovz">Override Z</label>
    </div>
    <label class="form-label">Price for Z</label>
    <input name="price_z" type="number" step="0.01" min="0" class="form-control" value="{{ '%.2f'|format(phone.price_z) if phone else '' }}">
  </div>
  <div class="col-12 d-flex gap-2">
    <button class="btn btn-primary">Save</button>
    <a class="btn btn-outline-secondary" href="{{ url_for('dashboard') }}">Cancel</a>
  </div>
</form>
{% endblock %}
"""

TPL_BULK = r"""
{% extends TPL_BASE %}
{% block content %}
<h4>Bulk Upload (CSV)</h4>
<p class="text-muted">Upload a CSV with columns: <code>brand,model,storage,color,condition,base_price,cost_price,stock,tags</code></p>
<form method="post" enctype="multipart/form-data" class="mb-4">
  <div class="input-group">
    <input type="file" class="form-control" name="file" accept=".csv" required>
    <button class="btn btn-primary" type="submit">Upload</button>
  </div>
</form>
<details>
  <summary>Sample CSV</summary>
  <pre>brand,model,storage,color,condition,base_price,cost_price,stock,tags
Apple,iPhone 12,128GB,Black,Good,350,280,5,
Samsung,Galaxy S21,256GB,Violet,New,450,360,3,reserved_b2b
Xiaomi,Redmi Note 10,64GB,Green,Scrap,60,40,1,
</pre>
</details>
{% endblock %}
"""
#cool
# Make base template available to others
app.jinja_env.globals['TPL_BASE'] = TPL_BASE


if __name__ == "__main__":
    init_db()
    app.run(debug=True)  # For demo; disable debug in production
