# app/routes/phones.py
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, current_app
from ..extensions import db
from ..models import Phone
from ..schemas import PhoneCreateSchema, PhoneUpdateSchema
from ..services.auth import require_api_key
from ..services.pricing import recommend_prices
from ..utils.csv_importer import parse_phone_rows

bp = Blueprint("phones", __name__)

@bp.get("/")
def list_phones_ui():
    phones = Phone.query.order_by(Phone.updated_at.desc()).all()
    return render_template("index.html", phones=phones)

@bp.get("/new")
def new_phone_form():
    # Render empty form for create (edit via separate route can be added later)
    return render_template("phone_form.html", phone=None)

@bp.post("/create")
@require_api_key
def create_phone():
    data = request.get_json(silent=True) or request.form.to_dict(flat=True)
    schema = PhoneCreateSchema()
    obj = schema.load(data)
    phone = Phone(**obj)

    overrides = {
        "X": obj.get("price_x"),
        "Y": obj.get("price_y"),
        "Z": obj.get("price_z"),
    }
    prices = recommend_prices(
        base_price=phone.base_price,
        fee_config=current_app.config["PLATFORM_FEES"],           # FIX: use current_app
        min_margin=current_app.config["PRICE_MIN_MARGIN"],        # FIX: use current_app
        manual_overrides=overrides,
    )
    phone.price_x, phone.price_y, phone.price_z = prices["X"], prices["Y"], prices["Z"]

    db.session.add(phone)
    db.session.commit()

    if request.is_json:
        return jsonify({"id": phone.id}), 201
    return redirect(url_for("phones.list_phones_ui"))

@bp.get("/<int:phone_id>")
def get_phone(phone_id):
    phone = Phone.query.get_or_404(phone_id)
    return jsonify({
        "id": phone.id, "brand": phone.brand, "model": phone.model,
        "condition": phone.condition, "base_price": phone.base_price,
        "stock_qty": phone.stock_qty, "price_x": phone.price_x,
        "price_y": phone.price_y, "price_z": phone.price_z,
        "tags": phone.tags, "discontinued": phone.discontinued
    })

@bp.post("/<int:phone_id>/update")
@require_api_key
def update_phone(phone_id):
    phone = Phone.query.get_or_404(phone_id)
    data = request.get_json(silent=True) or request.form.to_dict(flat=True)
    schema = PhoneUpdateSchema()
    obj = schema.load(data, partial=True)

    for k, v in obj.items():
        setattr(phone, k, v)

    overrides = {
        "X": obj.get("price_x"),
        "Y": obj.get("price_y"),
        "Z": obj.get("price_z"),
    }
    if any(k in obj for k in ("base_price", "price_x", "price_y", "price_z")):
        prices = recommend_prices(
            base_price=phone.base_price,
            fee_config=current_app.config["PLATFORM_FEES"],        # FIX: use current_app
            min_margin=current_app.config["PRICE_MIN_MARGIN"],     # FIX: use current_app
            manual_overrides=overrides,
        )
        phone.price_x, phone.price_y, phone.price_z = prices["X"], prices["Y"], prices["Z"]

    db.session.commit()
    if request.is_json:
        return jsonify({"ok": True})
    return redirect(url_for("phones.list_phones_ui"))

@bp.post("/<int:phone_id>/delete")
@require_api_key
def delete_phone(phone_id):
    phone = Phone.query.get_or_404(phone_id)
    db.session.delete(phone)
    db.session.commit()
    return jsonify({"ok": True})

@bp.get("/upload")
def upload_form():
    return render_template("upload.html")

@bp.post("/upload")
@require_api_key
def bulk_upload():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "file is required"}), 400

    created = 0
    for row in parse_phone_rows(f.stream):
        phone = Phone(**row)
        prices = recommend_prices(
            base_price=phone.base_price,
            fee_config=current_app.config["PLATFORM_FEES"],        # FIX: use current_app
            min_margin=current_app.config["PRICE_MIN_MARGIN"],     # FIX: use current_app
            manual_overrides={},
        )
        phone.price_x, phone.price_y, phone.price_z = prices["X"], prices["Y"], prices["Z"]
        db.session.add(phone)
        created += 1

    db.session.commit()
    return jsonify({"created": created})
