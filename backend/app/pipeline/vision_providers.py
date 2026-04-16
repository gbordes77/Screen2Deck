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
import json
from abc import ABC, abstractmethod
from typing import Any, List, Optional

import cv2
import numpy as np

from ..config import get_settings
from ..telemetry import logger

_S = get_settings()

# JSON schema used for Gemini `response_schema` / Anthropic tool-use, so
# the model returns a typed deck dict directly and we skip the fragile
# plain-text parsing step on the happy path.
_DECK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "main": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "qty": {"type": "integer", "minimum": 1, "maximum": 99},
                    "name": {"type": "string", "minLength": 1, "maxLength": 200},
                },
                "required": ["qty", "name"],
            },
        },
        "side": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "qty": {"type": "integer", "minimum": 1, "maximum": 99},
                    "name": {"type": "string", "minLength": 1, "maxLength": 200},
                },
                "required": ["qty", "name"],
            },
        },
    },
    "required": ["main", "side"],
}

_STRUCTURED_PROMPT = """You are extracting a Magic: The Gathering deck list from an image.

Return a JSON object with exactly two arrays, `main` and `side`, where
each element is `{"qty": <int>, "name": "<string>"}`.

Rules:
- Include every mainboard card and every sideboard card.
- Combine "Quantity: 4" stacking or "x2" suffixes into the qty field.
- MTGO exports the full 75 cards inline with no explicit sideboard
  marker; when a deck has exactly 75 cards, place the last 15 in `side`.
- For split / DFC / adventure cards use the full printed name with
  `//` between faces (e.g. `"Fire // Ice"`, `"Fable of the Mirror-Breaker // Reflection of Kiki-Jiki"`).
- Strip set codes and collector numbers — return the clean card name only.
- If the image contains no deck list, return `{"main": [], "side": []}`.
- Return nothing except the JSON object, no prose, no markdown fences.
"""

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


def _normalize_structured(payload: Any, provider: str) -> Optional[dict]:
    """Coerce a model's JSON response into ``{main, side, method}``.

    Accepts slightly loose shapes (JSON string, dict with main/side
    missing, qty as string) so we can still salvage a response that
    slightly deviates from the schema. Returns None if the payload
    doesn't contain any usable deck structure at all.
    """
    if payload is None:
        return None

    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode("utf-8")
        except Exception:
            return None

    if isinstance(payload, str):
        stripped = payload.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`").lstrip("json").strip()
        try:
            payload = json.loads(stripped)
        except Exception:
            return None

    if not isinstance(payload, dict):
        return None

    def _coerce(section: Any) -> list[dict]:
        if not isinstance(section, list):
            return []
        out: list[dict] = []
        for item in section:
            if not isinstance(item, dict):
                continue
            try:
                qty = int(item.get("qty") or item.get("quantity") or 0)
            except (TypeError, ValueError):
                continue
            name = (item.get("name") or item.get("card") or "").strip()
            if qty <= 0 or not name:
                continue
            out.append({"qty": qty, "name": name})
        return out

    main = _coerce(payload.get("main") or payload.get("mainboard") or [])
    side = _coerce(payload.get("side") or payload.get("sideboard") or [])

    if not main and not side:
        return None

    return {
        "main": main,
        "side": side,
        "method": f"vision_{provider}_structured",
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

    def extract_deck_structured(self, image: np.ndarray) -> Optional[dict]:
        """Run the Vision call with a JSON schema constraint.

        Subclasses override this with their vendor-specific
        structured-output API (Gemini ``response_schema`` / Anthropic
        tool-use). Return None when the model failed to produce a
        usable ``{main, side}`` payload so the caller can fall back
        to the plain-text ``extract_deck`` path.
        """
        return None

    @staticmethod
    def prompt() -> str:
        return _DEFAULT_PROMPT

    @staticmethod
    def structured_prompt() -> str:
        return _STRUCTURED_PROMPT


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

    def extract_deck_structured(self, image: np.ndarray) -> Optional[dict]:
        from google.genai import types

        image_bytes = _encode_jpeg(image)
        client = self._get_client()
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    self.structured_prompt(),
                ],
                # google-genai 1.x exposes two sibling fields on GenerateContentConfig:
                # - response_schema:       Gemini's native Schema type
                # - response_json_schema:  raw OpenAPI 3.1 / JSON Schema dict
                # _DECK_SCHEMA is a plain JSON Schema dict, so response_json_schema
                # is the canonical target. response_schema would require wrapping
                # in types.Schema(...) and expresses a subset of JSON Schema.
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=_DECK_SCHEMA,
                ),
            )
        except Exception as exc:
            logger.warning("Gemini structured call failed: %s", exc)
            return None

        content = getattr(response, "text", None)
        if content is None:
            content = getattr(response, "parsed", None)
        return _normalize_structured(content, provider=self.name)


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
            model or getattr(_S, "ANTHROPIC_MODEL", None) or "claude-haiku-4-5"
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

    def extract_deck_structured(self, image: np.ndarray) -> Optional[dict]:
        image_bytes = _encode_jpeg(image)
        encoded = base64.standard_b64encode(image_bytes).decode("ascii")
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=2048,
                tools=[
                    {
                        "name": "return_deck",
                        "description": (
                            "Return the extracted MTG deck list as a structured JSON "
                            "object with `main` and `side` arrays."
                        ),
                        "input_schema": _DECK_SCHEMA,
                    }
                ],
                tool_choice={"type": "tool", "name": "return_deck"},
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
                            {"type": "text", "text": self.structured_prompt()},
                        ],
                    }
                ],
            )
        except Exception as exc:
            logger.warning("Claude structured call failed: %s", exc)
            return None

        payload: Any = None
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", "") == "tool_use":
                payload = getattr(block, "input", None)
                break
        return _normalize_structured(payload, provider=self.name)


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


def run_vision_chain_structured(image: np.ndarray) -> Optional[dict]:
    """Try each provider's structured-output path and return the first
    usable ``{main, side, method}`` dict.

    Used by the Vision-primary pipeline to skip EasyOCR + regex parsing
    entirely. Returns None when every provider either failed the HTTP
    call or produced an unparseable response, so the caller can fall
    back to the traditional EasyOCR path.
    """
    chain = get_vision_chain()
    if not chain:
        return None

    for provider in chain:
        try:
            logger.info("Vision structured: trying %s", provider.name)
            result = provider.extract_deck_structured(image)
            if result and (result.get("main") or result.get("side")):
                logger.info(
                    "Vision structured: %s returned %d main / %d side cards",
                    provider.name,
                    len(result.get("main", [])),
                    len(result.get("side", [])),
                )
                return result
            logger.info("Vision structured: %s returned empty/invalid", provider.name)
        except Exception as exc:
            logger.warning("Vision structured: %s failed: %s", provider.name, exc)

    return None
