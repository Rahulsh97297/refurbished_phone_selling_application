from datetime import datetime
from .extensions import db

class Phone(db.Model):
    __tablename__ = "phones"
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(80), nullable=False, index=True)
    model = db.Column(db.String(120), nullable=False, index=True)
    storage = db.Column(db.String(40), nullable=True)
    color = db.Column(db.String(40), nullable=True)
    condition = db.Column(db.String(40), nullable=False)  # e.g., New/Good/Scrap
    base_price = db.Column(db.Float, nullable=False)       # your pre-fee base price
    stock_qty = db.Column(db.Integer, nullable=False, default=0)
    tags = db.Column(db.String(200), nullable=True)        # comma separated tags

    # Platform-specific price cache (auto-updated; can be manually overridden)
    price_x = db.Column(db.Float, nullable=True)
    price_y = db.Column(db.Float, nullable=True)
    price_z = db.Column(db.Float, nullable=True)

    # Administrative flags
    discontinued = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Listing(db.Model):
    __tablename__ = "listings"
    id = db.Column(db.Integer, primary_key=True)
    phone_id = db.Column(db.Integer, db.ForeignKey("phones.id"), nullable=False, index=True)
    platform = db.Column(db.String(10), nullable=False)  # X, Y, Z
    status = db.Column(db.String(20), nullable=False)    # success / failed
    reason = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    phone = db.relationship("Phone", backref="listings")
