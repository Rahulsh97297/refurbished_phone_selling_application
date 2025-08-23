from flask import Blueprint, request, jsonify
from ..models import Phone

bp = Blueprint("search", __name__)

@bp.get("/")
def search():
    q = (request.args.get("q") or "").strip().lower()
    cond = (request.args.get("condition") or "").strip()
    platform = (request.args.get("platform") or "").strip().upper()  # X/Y/Z

    query = Phone.query
    if q:
        like = f"%{q}%"
        query = query.filter((Phone.brand.ilike(like)) | (Phone.model.ilike(like)))
    if cond:
        query = query.filter(Phone.condition == cond)

    results = []
    for p in query.limit(100).all():
        # simple "listed" logic: if platform price exists and stock > 0 and not discontinued
        listed_on = []
        if p.price_x and p.stock_qty > 0 and not p.discontinued:
            listed_on.append("X")
        if p.price_y and p.stock_qty > 0 and not p.discontinued:
            listed_on.append("Y")
        if p.price_z and p.stock_qty > 0 and not p.discontinued:
            listed_on.append("Z")

        if platform and platform not in listed_on:
            continue

        results.append({
            "id": p.id, "brand": p.brand, "model": p.model, "condition": p.condition,
            "stock_qty": p.stock_qty, "listed_on": listed_on
        })
    return jsonify({"results": results})
