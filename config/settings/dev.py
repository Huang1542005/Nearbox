import os
import sys
from .base import *  # noqa: F401, F403

# Dev-specific overrides
DEBUG = True
ALLOWED_HOSTS = ["*"]

# Use in-memory SQLite when running pytest or when USE_SQLITE is set
if "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv) or os.environ.get("USE_SQLITE", "").lower() in ("true", "1"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

