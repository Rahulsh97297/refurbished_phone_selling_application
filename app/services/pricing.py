from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class FeeRule:
    type: str
    value: float
    fixed: float = 0.0

def apply_fee(price: float, rule: FeeRule) -> float:
    """
    Return final platform price that *charges the buyer* to achieve the given
    seller revenue `price` after platform fee deduction.
    For percent fee p: revenue = final*(1-p) -> final = revenue / (1-p)
    For percent_plus_fixed: revenue = final*(1-p) - fixed -> final = (revenue + fixed) / (1-p)
    """
    if rule.type == "percent":
        return round(price / (1.0 - rule.value), 2)
    if rule.type == "percent_plus_fixed":
        return round((price + rule.fixed) / (1.0 - rule.value), 2)
    raise ValueError("Unsupported fee rule")

def recommend_prices(
    base_price: float,
    fee_config: Dict[str, Dict],
    min_margin: float = 0.07,
    manual_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Compute platform prices ensuring at least `min_margin` margin above base.
    If manual_overrides provided (e.g., {'X': 199.99}), use them.
    """
    manual_overrides = manual_overrides or {}
    out = {}
    target_revenue = base_price * (1.0 + min_margin)

    for platform, cfg in fee_config.items():
        if platform in manual_overrides and manual_overrides[platform] > 0:
            out[platform] = round(manual_overrides[platform], 2)
            continue
        rule = FeeRule(type=cfg["type"], value=cfg["value"], fixed=cfg.get("fixed", 0.0))
        out[platform] = apply_fee(target_revenue, rule)
    return out

def is_profitable(final_price: float, base_price: float, fee_cfg: Dict) -> bool:
    """
    Check if listing is profitable: final_price - fees >= base_price
    """
    rule = FeeRule(type=fee_cfg["type"], value=fee_cfg["value"], fixed=fee_cfg.get("fixed", 0.0))
    # reverse: seller_revenue = final - fee
    if rule.type == "percent":
        seller_rev = final_price * (1 - rule.value)
    else:
        seller_rev = final_price * (1 - rule.value) - rule.fixed
    return seller_rev >= base_price
