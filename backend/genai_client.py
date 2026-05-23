"""OpenAI-compatible client for the enterprise GenAI Proxy API."""

from __future__ import annotations

import logging
import os
from typing import Any

from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

logger = logging.getLogger(__name__)

_client: OpenAI | None = None

DEFAULT_MODEL = "vertex_ai.gemini-2.5-flash"
DEFAULT_BASE_URL = "https://genai-sharedservice-americas.pwcinternal.com"


class GenAIClientError(Exception):
    """Raised when the GenAI proxy request fails; carries an HTTP-style status code."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_genai_config() -> dict[str, str]:
    return {
        "api_key": os.getenv("GENAI_API_KEY", "").strip(),
        "base_url": (os.getenv("GENAI_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL).rstrip("/"),
        "model": os.getenv("GENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
    }


def log_startup_config() -> None:
    config = get_genai_config()
    logger.info("GenAI model: %s", config["model"])
    logger.info("GenAI base URL: %s", config["base_url"])
    logger.info("GenAI API key configured: %s", bool(config["api_key"]))


def get_client() -> OpenAI:
    global _client
    config = get_genai_config()
    if not config["api_key"]:
        raise GenAIClientError(
            "GENAI_API_KEY is not configured.",
            status_code=500,
        )
    if _client is None:
        _client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
        )
    return _client


def _map_openai_error(exc: Exception) -> GenAIClientError:
    if isinstance(exc, AuthenticationError):
        return GenAIClientError(
            "Invalid GenAI API key. Check GENAI_API_KEY in backend/.env.",
            status_code=401,
        )
    if isinstance(exc, APIConnectionError):
        return GenAIClientError(
            "Could not reach the GenAI proxy. Check GENAI_BASE_URL and network access.",
            status_code=502,
        )
    if isinstance(exc, RateLimitError):
        return GenAIClientError(
            "GenAI API rate limit exceeded. Wait a moment and try again.",
            status_code=429,
        )
    if isinstance(exc, APIStatusError):
        status = exc.status_code or 502
        message = getattr(exc, "message", None) or str(exc)
        if status == 401:
            return GenAIClientError(
                "Invalid GenAI API key. Check GENAI_API_KEY in backend/.env.",
                status_code=401,
            )
        if status == 429:
            return GenAIClientError(
                "GenAI API rate limit exceeded. Wait a moment and try again.",
                status_code=429,
            )
        return GenAIClientError(f"GenAI API error ({status}): {message}", status_code=status)
    return GenAIClientError(f"GenAI service error: {exc}", status_code=502)


def chat_completions_create(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    response_format: dict[str, str] | None = None,
) -> str:
    """Call POST /v1/chat/completions via the OpenAI SDK and return assistant text."""
    config = get_genai_config()
    kwargs: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    try:
        client = get_client()
        response = client.chat.completions.create(**kwargs)
    except GenAIClientError:
        raise
    except Exception as exc:
        raise _map_openai_error(exc) from exc

    if not response.choices:
        raise GenAIClientError("GenAI API returned no choices.", status_code=502)

    content = response.choices[0].message.content
    if not content or not str(content).strip():
        raise GenAIClientError("GenAI API returned an empty response.", status_code=502)

    return str(content).strip()
