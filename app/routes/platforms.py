from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import Phone, Listing
from ..services.auth import require_api_key
from ..services.platforms import map_condition, should_block_for_stock, fee_cfg
from ..services.pricing import is_profitable, recommend_prices

bp = Blueprint("platforms", __name__)

@bp.post("/auto-update-prices")
@require_api_key
def auto_update_prices():
    """
    Recompute and store recommended platform prices for all phones (keeps manual overrides if passed per phone).
    """
    cfg = current_app.config["PLATFORM_FEES"]
    min_margin = current_app.config["PRICE_MIN_MARGIN"]
    updated = 0
    for p in Phone.query.all():
        prices = recommend_prices(p.base_price, cfg, min_margin, {})
        p.price_x, p.price_y, p.price_z = prices["X"], prices["Y"], prices["Z"]
        updated += 1
    db.session.commit()
    return jsonify({"updated": updated})

@bp.post("/list/<platform>/<int:phone_id>")
@require_api_key
def list_phone(platform, phone_id):
    platform = platform.upper()
    if platform not in {"X", "Y", "Z"}:
        return jsonify({"error": "Unknown platform"}), 400

    phone = Phone.query.get_or_404(phone_id)

    # Block if no stock or discontinued
    blocked, reason = should_block_for_stock(phone.stock_qty, phone.discontinued)
    if blocked:
        lst = Listing(phone_id=phone.id, platform=platform, status="failed", reason=reason)
        db.session.add(lst); db.session.commit()
        return jsonify({"status": "failed", "reason": reason}), 400

    # Map condition
    ok, mapped = map_condition(platform, phone.condition)
    if not ok:
        lst = Listing(phone_id=phone.id, platform=platform, status="failed", reason=mapped)
        db.session.add(lst); db.session.commit()
        return jsonify({"status": "failed", "reason": mapped}), 400

    # Price presence + profitability check
    price_attr = f"price_{platform.lower()}"
    final_price = getattr(phone, price_attr)
    if not final_price:
        return jsonify({"status": "failed", "reason": "Missing platform price"}), 400

    if not is_profitable(final_price, phone.base_price, fee_cfg(platform)):
        reason = "Unprofitable after platform fees"
        lst = Listing(phone_id=phone.id, platform=platform, status="failed", reason=reason)
        db.session.add(lst); db.session.commit()
        return jsonify({"status": "failed", "reason": reason}), 400

    # Simulate success
    lst = Listing(phone_id=phone.id, platform=platform, status="success", reason=f"Listed as '{mapped}'")
    db.session.add(lst)
    db.session.commit()
    return jsonify({"status": "success", "platform": platform, "condition_label": mapped, "price": final_price})
