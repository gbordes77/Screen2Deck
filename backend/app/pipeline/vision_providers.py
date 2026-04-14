"""
Vision OCR providers for Screen2Deck.

When EasyOCR falls below confidence thresholds we fall back to a
multimodal LLM. The codebase originally shipped with a single OpenAI
path; this module introduces a small provider abstraction so that
operators can pick between modern vendors without touching the
pipeline code.

Default chain: Gemini 3.1 Flash-Lite (primary) → Claude Haiku 4.5 (fallback).

Configuration:
  VISION_PROVIDER=gemini,claude            # comma-separated chain, in priority order
  GEMINI_API_KEY=...
  ANTHROPIC_API_KEY=...
  GEMINI_MODEL=gemini-3.1-flash-lite-preview  # optional override
  ANTHROPIC_MODEL=claude-haiku-4-5
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from typing import List, Optional

import cv2
import numpy as np

from ..config import get_settings
from ..telemetry import logger

_S = get_settings()

_DEFAULT_PROMPT = """Extract every Magic: The Gathering card visible in this image.

Return the result as a plain text deck list, one card per line, with the
format:

4 Lightning Bolt
2 Counterspell

Rules:
- Include basic lands and sideboard cards.
- For MTG Arena screenshots where quantities appear as "x2" or "x3" next
  to card art, combine them into the leading number.
- If a sideboard is visible, insert a line containing exactly the word
  "Sideboard" before the sideboard cards.
- Do not add commentary, markdown, or explanations — only the deck list.
"""


def _encode_jpeg(image: np.ndarray) -> bytes:
    """Encode an OpenCV BGR array as JPEG bytes for the Vision API."""
    ok, buffer = cv2.imencode(".jpg", image)
    if not ok:
        raise ValueError("Failed to encode image for Vision API")
    return buffer.tobytes()


def _parse_text_response(content: str, provider: str) -> dict:
    """Convert a plain-text deck list into the OCR-span format the rest of
    the pipeline expects."""
    spans = []
    for raw_line in (content or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        spans.append({"text": line, "conf": 0.95})
    return {
        "spans": spans,
        "mean_conf": 0.95 if spans else 0.0,
        "fallback_used": bool(spans),
        "method": f"vision_{provider}",
    }


class VisionProvider(ABC):
    """Abstract Vision OCR provider."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured and the SDK is importable."""

    @abstractmethod
    def extract_deck(self, image: np.ndarray) -> dict:
        """Run the Vision call and return an OCR-format dict."""

    @staticmethod
    def prompt() -> str:
        return _DEFAULT_PROMPT


class GeminiVisionProvider(VisionProvider):
    """Gemini 3.1 Flash-Lite — best cost/speed/quality combo for image OCR (April 2026).

    At $0.25/$1.50 per 1M input/output tokens and ~258 tokens per image,
    a Vision fallback call costs roughly $0.00008, or $0.08 per 1000
    deck scans — well under the budget of any project that still has
    EasyOCR as its primary path.
    """

    name = "gemini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or getattr(_S, "GEMINI_API_KEY", None)
        self._model = (
            model
            or getattr(_S, "GEMINI_MODEL", None)
            or "gemini-3.1-flash-lite-preview"
        )
        self._client = None

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import google.genai  # noqa: F401
        except ImportError:
            logger.warning("google-genai not installed; Gemini provider unavailable")
            return False
        return True

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def extract_deck(self, image: np.ndarray) -> dict:
        from google.genai import types

        image_bytes = _encode_jpeg(image)
        client = self._get_client()
        response = client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                self.prompt(),
            ],
        )
        content = getattr(response, "text", "") or ""
        return _parse_text_response(content, provider=self.name)


class ClaudeVisionProvider(VisionProvider):
    """Claude Haiku 4.5 — secondary fallback, strong format adherence."""

    name = "claude"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or getattr(_S, "ANTHROPIC_API_KEY", None)
        self._model = (
            model
            or getattr(_S, "ANTHROPIC_MODEL", None)
            or "claude-haiku-4-5"
        )
        self._client = None

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            logger.warning("anthropic not installed; Claude provider unavailable")
            return False
        return True

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def extract_deck(self, image: np.ndarray) -> dict:
        image_bytes = _encode_jpeg(image)
        encoded = base64.standard_b64encode(image_bytes).decode("ascii")
        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": encoded,
                            },
                        },
                        {"type": "text", "text": self.prompt()},
                    ],
                }
            ],
        )
        content = "".join(
            getattr(block, "text", "") for block in getattr(response, "content", [])
        )
        return _parse_text_response(content, provider=self.name)


_REGISTRY: dict[str, type[VisionProvider]] = {
    "gemini": GeminiVisionProvider,
    "claude": ClaudeVisionProvider,
}


def get_vision_chain() -> List[VisionProvider]:
    """Return the ordered list of configured, importable Vision providers.

    The order is read from `VISION_PROVIDER` (comma-separated), defaulting
    to ``gemini,claude``. Providers that aren't configured (missing API
    key) or whose SDK is not installed are silently skipped.
    """
    order_raw = getattr(_S, "VISION_PROVIDER", None) or "gemini,claude"
    order = [p.strip().lower() for p in order_raw.split(",") if p.strip()]

    chain: List[VisionProvider] = []
    for name in order:
        cls = _REGISTRY.get(name)
        if cls is None:
            logger.warning("Unknown Vision provider '%s' in VISION_PROVIDER", name)
            continue
        provider = cls()
        if provider.is_available():
            chain.append(provider)
        else:
            logger.info("Vision provider '%s' not available (missing key or SDK)", name)
    return chain


def run_vision_chain(image: np.ndarray) -> dict:
    """Try each configured Vision provider in order until one succeeds.

    Returns the OCR-span dict from the first provider that returns at
    least one span, or an empty-fallback dict if every provider failed.
    """
    chain = get_vision_chain()
    if not chain:
        logger.warning("No Vision provider available; returning empty fallback")
        return {
            "spans": [],
            "mean_conf": 0.0,
            "fallback_used": False,
            "method": "none",
        }

    for provider in chain:
        try:
            logger.info("Vision fallback: trying %s", provider.name)
            result = provider.extract_deck(image)
            if result.get("spans"):
                logger.info(
                    "Vision fallback: %s returned %d spans",
                    provider.name,
                    len(result["spans"]),
                )
                return result
            logger.warning("Vision fallback: %s returned 0 spans", provider.name)
        except Exception as exc:
            logger.warning("Vision fallback: %s failed: %s", provider.name, exc)

    logger.error("Vision fallback: every provider failed")
    return {
        "spans": [],
        "mean_conf": 0.0,
        "fallback_used": False,
        "method": "failed",
    }
