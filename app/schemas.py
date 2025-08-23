from marshmallow import Schema, fields, validates, ValidationError

VALID_CONDITIONS = {"New", "Good", "Scrap"}

class PhoneCreateSchema(Schema):
    brand = fields.String(required=True)
    model = fields.String(required=True)
    storage = fields.String(load_default=None)
    color = fields.String(load_default=None)
    condition = fields.String(required=True)
    base_price = fields.Float(required=True)
    stock_qty = fields.Integer(required=True)
    tags = fields.String(load_default=None)
    discontinued = fields.Boolean(load_default=False)
    price_x = fields.Float(load_default=None)
    price_y = fields.Float(load_default=None)
    price_z = fields.Float(load_default=None)

    @validates("condition")
    def validate_condition(self, v):
        if v not in VALID_CONDITIONS:
            raise ValidationError(f"condition must be one of {sorted(VALID_CONDITIONS)}")

    @validates("base_price")
    def validate_price(self, v):
        if v <= 0:
            raise ValidationError("base_price must be > 0")

    @validates("stock_qty")
    def validate_stock(self, v):
        if v < 0:
            raise ValidationError("stock_qty must be >= 0")


class PhoneUpdateSchema(PhoneCreateSchema):
    # All fields optional for update
    brand = fields.String(load_default=None)
    model = fields.String(load_default=None)
    condition = fields.String(load_default=None)
    base_price = fields.Float(load_default=None)
    stock_qty = fields.Integer(load_default=None)
