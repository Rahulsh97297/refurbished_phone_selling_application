# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from marshmallow import ValidationError
from flask import jsonify
from marshmallow import Schema, fields

db = SQLAlchemy()
# we don't need flask_marshmallow; plain marshmallow is enough
# schemas are defined in app/schemas.py using Schema/fields directly

# Optional: global Marshmallow error handler helper (used in routes if desired)
def handle_validation_error(err: ValidationError):
    return jsonify({"errors": err.messages}), 400
