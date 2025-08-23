import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.sqlite")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    # Pricing knobs (easy to tune)
    PRICE_MIN_MARGIN = 0.07  # 7% target margin after fees
    # Platform fee rules (can be overridden or extended)
    PLATFORM_FEES = {
        "X": {"type": "percent", "value": 0.10},                # 10%
        "Y": {"type": "percent_plus_fixed", "value": 0.08, "fixed": 2.0},  # 8% + $2
        "Z": {"type": "percent", "value": 0.12},                # 12%
    }
