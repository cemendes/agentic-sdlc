import os
import json

_secrets_cache = None

def get_setting(key: str, default: str = "") -> str:
    global _secrets_cache
    if _secrets_cache is None:
        _secrets_cache = {}
        secrets_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "secrets.json"))
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, "r") as f:
                    _secrets_cache = json.load(f)
            except Exception:
                pass
        elif os.path.exists("secrets.json"):
            try:
                with open("secrets.json", "r") as f:
                    _secrets_cache = json.load(f)
            except Exception:
                pass

    if key in _secrets_cache:
        return _secrets_cache[key]
    return os.environ.get(key, default)
