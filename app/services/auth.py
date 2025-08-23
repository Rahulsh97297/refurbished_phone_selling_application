from functools import wraps
from flask import request, jsonify
import os

def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.getenv("API_KEY")
        provided = request.headers.get("X-API-KEY")
        if not expected or provided != expected:
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper
