import csv
from typing import Iterable, Dict

REQUIRED_FIELDS = {"brand", "model", "condition", "base_price", "stock_qty"}

def parse_phone_rows(file_stream) -> Iterable[Dict]:
    """
    Accepts a file-like object of CSV.
    Returns iterable of validated dict rows (lightweight checks).
    """
    reader = csv.DictReader((line.decode("utf-8", "ignore") for line in file_stream))
    for i, row in enumerate(reader, start=2):  # start=2 to account for header line
        if not REQUIRED_FIELDS.issubset(set(k.strip() for k in row.keys())):
            raise ValueError(f"CSV header missing required fields {REQUIRED_FIELDS}")
        # basic normalization
        out = {
            "brand": (row.get("brand") or "").strip(),
            "model": (row.get("model") or "").strip(),
            "storage": (row.get("storage") or "").strip() or None,
            "color": (row.get("color") or "").strip() or None,
            "condition": (row.get("condition") or "").strip() or "Good",
            "base_price": float(row.get("base_price") or 0),
            "stock_qty": int(row.get("stock_qty") or 0),
            "tags": (row.get("tags") or "").strip() or None,
            "discontinued": str(row.get("discontinued") or "").lower() in {"1", "true", "yes"},
        }
        if not out["brand"] or not out["model"]:
            raise ValueError(f"Row {i}: brand/model cannot be empty")
        yield out
