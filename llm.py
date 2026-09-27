"""Single entry point for every model call.

Handles the free-tier limits of the primary model (requests per minute and per
day), retries on server errors, never returns the model's internal "thought"
text as an answer, and falls back to a second model when the primary's quota
is exhausted.
"""
import datetime
import json
import os
import re
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Optional
from zoneinfo import ZoneInfo

import httpx
from google.genai import types
from google.genai.errors import ClientError, ServerError
from pydantic import TypeAdapter, ValidationError

import config
from config import client

# Free-tier daily quotas reset at midnight Pacific time.
QUOTA_TZ = ZoneInfo("America/Los_Angeles")
USAGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bifas_usage.json")

SERVER_RETRY_DELAYS = (2, 6)
FALLBACK_EXTRA_TOKENS = 2048  # the fallback thinks without a controllable budget
PER_MINUTE_BACKOFF_SECONDS = 60


class RateLimiter:
    def __init__(self, max_per_minute=15):
        self.max_per_minute = max_per_minute
        self.min_interval = 60.0 / max_per_minute
        self.last_call = 0
        self.lock = Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_call = time.time()


class DailyCounter:
    """Counts primary-model requests per quota day, persisted so restarts don't reset it."""

    def __init__(self, limit, path=USAGE_FILE):
        self.limit = limit
        self.path = path
        self.lock = Lock()
        self.day, self.count = self._load()

    @staticmethod
    def _today():
        return datetime.datetime.now(QUOTA_TZ).date().isoformat()

    def _load(self):
        try:
            with open(self.path) as f:
                data = json.load(f)
            if data.get("day") == self._today():
                return data["day"], int(data.get("count", 0))
        except (OSError, ValueError, KeyError):
            pass
        return self._today(), 0

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump({"day": self.day, "count": self.count}, f)
        except OSError:
            pass

    def _roll(self):
        today = self._today()
        if today != self.day:
            self.day, self.count = today, 0

    def try_acquire(self):
        with self.lock:
            self._roll()
            if self.count >= self.limit:
                return False
            self.count += 1
            self._save()
            return True

    def mark_exhausted(self):
        with self.lock:
            self._roll()
            self.count = max(self.count, self.limit)
            self._save()

    def used(self):
        with self.lock:
            self._roll()
            return self.count


@dataclass
class LLMResult:
    text: str
    parsed: Any
    model: str
    finish_reason: Optional[str]
    fallback: bool


_limiters = {}
_limiters_lock = Lock()
daily_counter = DailyCounter(config.DAILY_REQUEST_LIMIT)
_fallback_until = 0.0  # epoch seconds; primary is skipped until then
_fallback_lock = Lock()


def _limiter(model):
    with _limiters_lock:
        if model not in _limiters:
            _limiters[model] = RateLimiter(config.REQUESTS_PER_MINUTE)
        return _limiters[model]


def _next_quota_reset():
    now = datetime.datetime.now(QUOTA_TZ)
    tomorrow = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return tomorrow.timestamp()


def _switch_to_fallback(until):
    global _fallback_until
    with _fallback_lock:
        _fallback_until = max(_fallback_until, until)


def _primary_available():
    return time.time() >= _fallback_until


def _is_daily_quota_error(error):
    return "PerDay" in str(error) or "per day" in str(error).lower()


def extract_text(response):
    """Answer text only: thought parts are never returned as the answer."""
    try:
        parts = response.candidates[0].content.parts or []
    except (AttributeError, IndexError, TypeError):
        return ""
    return "".join(p.text for p in parts if p.text and not getattr(p, "thought", False)).strip()


def _finish_reason(response):
    try:
        reason = response.candidates[0].finish_reason
        return getattr(reason, "name", str(reason)) if reason is not None else None
    except (AttributeError, IndexError, TypeError):
        return None


def extract_json_from_response(raw_text):
    """Extract JSON from response, handling markdown code blocks and empty responses."""
    if not raw_text:
        return None

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def _parse(response, text, schema, fallback):
    if schema is None:
        return None
    if not fallback and getattr(response, "parsed", None) is not None:
        return response.parsed
    data = extract_json_from_response(text)
    if data is None:
        return None
    try:
        return TypeAdapter(schema).validate_python(data)
    except ValidationError:
        return None


def _build_request(prompt, model, max_tokens, schema, thinking, fallback):
    if fallback:
        # The fallback may not support structured output or thinking levels:
        # describe the schema in the prompt and leave room for its thinking.
        if schema is not None:
            json_schema = json.dumps(TypeAdapter(schema).json_schema())
            prompt = f"{prompt}\n\nRespond with ONLY valid JSON matching this JSON schema:\n{json_schema}"
        cfg = types.GenerateContentConfig(max_output_tokens=max_tokens + FALLBACK_EXTRA_TOKENS)
        return prompt, cfg
    cfg = types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_level=thinking),
    )
    if schema is not None:
        cfg.response_mime_type = "application/json"
        cfg.response_schema = schema
    return prompt, cfg


def generate(prompt, *, max_tokens, schema=None, thinking="low"):
    """Call the model and return an LLMResult.

    schema: a Pydantic model or type (e.g. list[Task]); the result's `parsed` holds
    validated data, or None if the model's output didn't match.
    thinking: "minimal" | "low" | "medium" | "high" (primary model only).
    """
    budget = max_tokens
    server_errors = 0
    truncation_retried = False

    while True:
        fallback = not _primary_available()
        if not fallback and not daily_counter.try_acquire():
            _switch_to_fallback(_next_quota_reset())
            fallback = True
        model = config.FALLBACK_MODEL if fallback else config.PRIMARY_MODEL

        contents, cfg = _build_request(prompt, model, budget, schema, thinking, fallback)
        _limiter(model).wait()
        try:
            response = client.models.generate_content(model=model, contents=contents, config=cfg)
        except ClientError as e:
            if e.code == 429 and not fallback:
                if _is_daily_quota_error(e):
                    daily_counter.mark_exhausted()
                    _switch_to_fallback(_next_quota_reset())
                else:
                    _switch_to_fallback(time.time() + PER_MINUTE_BACKOFF_SECONDS)
                continue
            raise
        except (ServerError, httpx.TransportError):
            if server_errors < len(SERVER_RETRY_DELAYS):
                time.sleep(SERVER_RETRY_DELAYS[server_errors])
                server_errors += 1
                continue
            raise

        text = extract_text(response)
        if not text and not truncation_retried:
            # Only thoughts came back (budget spent thinking) or the output was cut off.
            budget *= 2
            truncation_retried = True
            continue

        return LLMResult(
            text=text,
            parsed=_parse(response, text, schema, fallback),
            model=model,
            finish_reason=_finish_reason(response),
            fallback=fallback,
        )


def usage_snapshot():
    """Today's primary-model usage, for display in the UI."""
    return {
        "used": daily_counter.used(),
        "limit": daily_counter.limit,
        "primary_model": config.PRIMARY_MODEL,
        "fallback_model": config.FALLBACK_MODEL,
        "fallback_active": not _primary_available(),
    }
