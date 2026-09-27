import os
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError(
        "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your "
        "Google AI Studio key (https://aistudio.google.com/apikey)."
    )

# Primary model and its free-tier limits; the fallback has its own separate quota.
PRIMARY_MODEL = os.getenv("BIFAS_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODEL = os.getenv("BIFAS_FALLBACK_MODEL", "gemma-4-31b-it")
REQUESTS_PER_MINUTE = int(os.getenv("BIFAS_RPM", "15"))
DAILY_REQUEST_LIMIT = int(os.getenv("BIFAS_DAILY_LIMIT", "500"))

# Per-request HTTP timeout so one hung call cannot stall the pipeline.
REQUEST_TIMEOUT_MS = int(os.getenv("BIFAS_REQUEST_TIMEOUT_MS", "90000"))

client = genai.Client(
    api_key=GOOGLE_API_KEY,
    http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
)
