"""Central settings. Everything is read from environment variables / the .env file.

Never hard-code keys in source files (the original project did, which is how keys leak).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# ---- Identity -------------------------------------------------------------
USER_NAME = _get("USER_NAME", "Prajwal")          # who Jarvis is talking to
ASSISTANT_NAME = _get("ASSISTANT_NAME", "Jarvis")

# ---- LLM (Groq, free tier) --------------------------------------------------
GROQ_API_KEY = _get("GROQ_API_KEY")
GROQ_BASE_URL = _get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = _get("GROQ_MODEL", "llama-3.3-70b-versatile")
# If the main model is rate limited / retired, Jarvis quietly tries these next.
GROQ_FALLBACK_MODELS = [
    m.strip()
    for m in _get("GROQ_FALLBACK_MODELS", "openai/gpt-oss-120b,llama-3.1-8b-instant").split(",")
    if m.strip()
]

# ---- Optional free keys (everything works without them) --------------------
GNEWS_API_KEY = _get("GNEWS_API_KEY")                  # https://gnews.io
SEMANTIC_SCHOLAR_API_KEY = _get("SEMANTIC_SCHOLAR_API_KEY")

# ---- Defaults ---------------------------------------------------------------
DEFAULT_CITY = _get("DEFAULT_CITY", "Pune")
DEFAULT_COUNTRY = _get("DEFAULT_COUNTRY", "in").lower()   # news edition
TIMEZONE = _get("TIMEZONE", "Asia/Kolkata")

# ---- Server safety (matters once you host it publicly) ----------------------
APP_PIN = _get("APP_PIN")                              # optional: protect your Jarvis
RATE_LIMIT_PER_MIN = int(_get("RATE_LIMIT_PER_MIN", "20") or 20)

# ---- Desktop voice mode ------------------------------------------------------
MUSIC_PATH = _get("MUSIC_PATH")                        # e.g. C:\Users\Prajwal\Music\song.mp3


def groq_models() -> list[str]:
    seen, out = set(), []
    for m in [GROQ_MODEL, *GROQ_FALLBACK_MODELS]:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out
