from typing import Tuple, Dict
from flask import current_app

# Condition mapping per platform (assignment)
# X: New, Good, Scrap
# Y: 3 stars (Excellent), 2 stars (Good), 1 star (Usable)
# Z: New, As New, Good

COND_MAP = {
    "X": {"New": "New", "Good": "Good", "Scrap": "Scrap"},
    "Y": {"New": "3 stars (Excellent)", "Good": "2 stars (Good)", "Scrap": "1 star (Usable)"},
    "Z": {"New": "New", "Good": "Good", "Scrap": "As New"},  # business choice for Scrap -> As New (or reject)
}

def map_condition(platform: str, condition: str) -> Tuple[bool, str]:
    mapping = COND_MAP.get(platform)
    if not mapping or condition not in mapping:
        return False, f"Unsupported condition '{condition}' for {platform}"
    return True, mapping[condition]

def should_block_for_stock(stock_qty: int, discontinued: bool) -> Tuple[bool, str]:
    if discontinued:
        return True, "Product discontinued"
    if stock_qty <= 0:
        return True, "Out of stock"
    return False, ""

def fee_cfg(platform: str) -> Dict:
    return current_app.config["PLATFORM_FEES"][platform]
