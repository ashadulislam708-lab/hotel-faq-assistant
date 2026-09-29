"""Environment/config loading for the Hotel FAQ Assistant backend."""

import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")


def require_config(*names: str):
    """Raise a clear error if any of the named config values are unset."""
    missing = [name for name in names if not globals().get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in backend/.env."
        )
