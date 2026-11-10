"""
StudyMind AI — Modern Gemini API Client using google.genai SDK
Provides:
- Native JSON mode with strict validation and auto-repair
- Live streaming with robust model fallback and transient error retries
- Multi-turn conversation chat
- Multimodal OCR support
- FastMCP tool calling bridge
"""
import functools
import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, Generator, List, Optional, Union

from google import genai
from google.genai import types, errors

from config import GEMINI_API_KEY as DEFAULT_KEY, GEMINI_MODEL

logger = logging.getLogger("StudyMind.GeminiClient")

# Model fallback chain in case the primary model is busy, rate-limited, or unavailable
_raw_models = [
    GEMINI_MODEL,
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
]
# Deduplicate while preserving order
FALLBACK_MODELS = list(dict.fromkeys([m for m in _raw_models if m]))

# Cached genai.Client instance mapped by API key
_client_cache: Dict[str, genai.Client] = {}


def _safe_cache(func: Callable) -> Callable:
    """
    Conditionally applies @st.cache_data when running inside an active Streamlit server,
    or falls back to a clean passthrough decorator in test/CLI mode.
    """
    try:
        import streamlit as st
        from streamlit.runtime import get_instance
        if get_instance() is not None:
            return st.cache_data(show_spinner=False)(func)
    except Exception:
        pass
    return func


def get_api_key() -> str:
    """Retrieve API key from Streamlit session state, os env, or config."""
    try:
        import streamlit as st
        if st.session_state.get("gemini_api_key"):
            key = st.session_state["gemini_api_key"].strip()
            if key:
                return key
    except Exception:
        pass
    env_k = os.getenv("GEMINI_API_KEY", "").strip()
    if env_k:
        return env_k
    return (DEFAULT_KEY or "").strip()


def get_genai_client(api_key: Optional[str] = None) -> genai.Client:
    """
    Returns an initialized google.genai.Client with the current API key.
    Reuses existing client instances for connection pooling.
    """
    key = (api_key or get_api_key()).strip()
    if not key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Enter your key in the sidebar or add it to .env."
        )

    if key not in _client_cache:
        _client_cache[key] = genai.Client(api_key=key)
    return _client_cache[key]


def _is_permanent_error(err_str: str) -> bool:
    """Determine if an API error is permanent (do not retry)."""
    s = err_str.upper()
    return any(term in s for term in [
        "API_KEY_INVALID", "API KEY NOT VALID", "PERMISSION_DENIED",
        "INVALID_ARGUMENT", "400", "401", "403"
    ]) and "RESOURCE_EXHAUSTED" not in s and "429" not in s


def _is_transient_error(err_str: str) -> bool:
    """Determine if an API error is transient (can retry with backoff)."""
    s = err_str.upper()
    return any(term in s for term in [
        "RESOURCE_EXHAUSTED", "429", "UNAVAILABLE", "503",
        "DEADLINE_EXCEEDED", "504", "TIMEOUT", "CONNECTTIMEOUT",
        "READTIMEOUT", "INTERNAL", "500", "RESET BY PEER"
    ])


def _strip_to_json(text: str) -> str:
    """
    Strip any markdown wrappers and extract raw JSON.
    Handles: ```json ... ```, ``` ... ```, or plain text with leading/trailing noise.
    """
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def _repair_truncated_json(raw: str) -> str:
    """
    Repairs truncated JSON strings (e.g. from token limit cutoff)
    by removing incomplete trailing tokens and balancing unclosed brackets and braces.
    """
    s = _strip_to_json(raw)
    s = re.sub(r',\s*"[^"]*"?\s*:?\s*[^,}\]]*$', '', s)
    s = re.sub(r',\s*$', '', s)

    stack = []
    in_str = False
    escape = False
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch in ('{', '['):
                stack.append(ch)
            elif ch == '}' and stack and stack[-1] == '{':
                stack.pop()
            elif ch == ']' and stack and stack[-1] == '[':
                stack.pop()

    if in_str:
        s += '"'
    s = re.sub(r',\s*$', '', s)
    while stack:
        open_ch = stack.pop()
        if open_ch == '{':
            s += '}'
        elif open_ch == '[':
            s += ']'
    return s


def _execute_with_model_fallback(generate_fn: Callable) -> Any:
    """
    Executes a Gemini generation function against the fallback model chain.
    Applies exponential backoff for transient errors (429, 503, 504) and fails
    immediately on permanent authentication errors.
    """
    last_error = None
    for model_name in FALLBACK_MODELS:
        # Retry transient errors up to 2 times per model with backoff
        for attempt in range(2):
            try:
                return generate_fn(model_name)
            except Exception as e:
                err_msg = str(e)
                last_error = e

                # Check for permanent authentication/permission errors
                if _is_permanent_error(err_msg):
                    raise ValueError(
                        f"Gemini API Error ({err_msg[:120]})\n\n"
                        "💡 Please verify your API key at https://aistudio.google.com/ "
                        "(Google AI Studio keys typically begin with 'AIzaSy...')."
                    )

                # Check for transient errors
                if _is_transient_error(err_msg):
                    wait_time = 1.0 * (attempt + 1)
                    logger.warning(
                        f"Model '{model_name}' encountered transient error ({err_msg[:60]}). "
                        f"Retrying in {wait_time}s (attempt {attempt+1}/2)..."
                    )
                    time.sleep(wait_time)
                    continue

                # 404 NOT_FOUND or unknown model error: do not retry same model, move to next
                if "NOT_FOUND" in err_msg.upper() or "404" in err_msg:
                    logger.warning(f"Model '{model_name}' not available (404). Trying next fallback model...")
                    break

                # Other unknown error: log and try next model
                logger.warning(f"Model '{model_name}' failed with {type(e).__name__}: {err_msg[:80]}. Trying next model...")
                break

    raise last_error or RuntimeError("All Gemini fallback models exhausted.")


@_safe_cache
def call_gemini_json(prompt: str, temperature: float = 0.3, max_tokens: int = 4096) -> dict:
    """
    Call Gemini in native constrained JSON mode with automatic model fallback.
    """
    client = get_genai_client()

    def _call(model_name: str):
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            max_output_tokens=max_tokens,
        )
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        raw = response.text or ""
        cleaned = _strip_to_json(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            repaired = _repair_truncated_json(raw)
            return json.loads(repaired)

    try:
        return _execute_with_model_fallback(_call)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}")


@_safe_cache
def call_gemini_text(prompt: str, temperature: float = 0.8, max_tokens: int = 4096) -> str:
    """
    Call Gemini and return plain text (for chatbot, briefing, onboarding).
    """
    client = get_genai_client()

    def _call(model_name: str):
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        return response.text or ""

    return _execute_with_model_fallback(_call)


def call_gemini_chat(messages: list, system_prompt: str = "", temperature: float = 0.8) -> str:
    """
    Multi-turn chat call. messages = [{"role": "user"|"model"|"assistant", "content": "..."}]
    """
    client = get_genai_client()

    contents = []
    for m in messages:
        role = "model" if m.get("role") in ("model", "assistant") else "user"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=m.get("content", ""))]
            )
        )

    def _call(model_name: str):
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=8192,
            system_instruction=system_prompt if system_prompt else None,
        )
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        return response.text or ""

    return _execute_with_model_fallback(_call)


def call_gemini_stream(
    prompt: str,
    temperature: float = 0.7,
    system_prompt: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    Call Gemini with stream=True. Yields text chunks live as they arrive.
    Compatible with Streamlit's st.write_stream().

    Features:
    - In-generator model fallback: if a model fails at the start of streaming (504, 503, 429),
      it seamlessly tries the next fallback model.
    - Non-streaming fallback: if streaming fails completely, it returns the complete
      text response without crashing the UI.
    """
    client = get_genai_client()
    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=4096,
        system_instruction=system_prompt if system_prompt else None,
    )

    yielded_any = False
    last_error = None

    for model_name in FALLBACK_MODELS:
        try:
            stream = client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=config,
            )

            # Peek first chunk to verify stream establishes connection
            stream_iter = iter(stream)
            try:
                first_chunk = next(stream_iter)
            except StopIteration:
                # Empty stream
                continue

            if first_chunk.text:
                yielded_any = True
                yield first_chunk.text

            for chunk in stream_iter:
                try:
                    if chunk.text:
                        yielded_any = True
                        yield chunk.text
                except (ValueError, StopIteration):
                    continue
                except Exception as chunk_err:
                    logger.warning(f"Stream interrupted mid-generation on {model_name}: {chunk_err}")
                    break

            if yielded_any:
                return

        except Exception as e:
            err_msg = str(e)
            last_error = e

            # If chunks were already yielded to the user, we cannot restart the stream
            if yielded_any:
                logger.warning(f"Streaming error after partial response: {err_msg[:80]}")
                return

            if _is_permanent_error(err_msg):
                raise ValueError(
                    f"Gemini API Key Error: {err_msg[:120]}\n\n"
                    "💡 Please verify your API key in the sidebar or update your .env file."
                )

            logger.warning(f"Streaming failed on '{model_name}' ({err_msg[:80]}). Switching to fallback model...")
            continue

    # Final safety: If streaming never yielded anything, attempt safe non-streaming call
    if not yielded_any:
        logger.info("Attempting non-streaming fallback for chat response...")
        try:
            fallback_text = call_gemini_text(prompt, temperature=temperature)
            if fallback_text:
                yield fallback_text
                return
        except Exception as text_fallback_err:
            logger.error(f"Non-streaming fallback also failed: {text_fallback_err}")
            raise last_error or text_fallback_err


def call_gemini_with_mcp(
    prompt: str,
    tool_names: Optional[List[str]] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    """
    Direct Model Context Protocol (MCP) tool-calling bridge for Gemini.
    Translates MCP tools into Gemini-callable functions, runs multi-turn tool calling,
    and returns the model's synthesized result.
    """
    from mcp_client import mcp_client

    tools = mcp_client.get_tool_callables(tool_names)
    client = get_genai_client()

    def _call(model_name: str):
        config = types.GenerateContentConfig(
            temperature=temperature,
            tools=tools if tools else None,
            system_instruction=system_prompt,
        )
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )
        return response.text or ""

    return _execute_with_model_fallback(_call)


# ── Backwards-Compatible Model Adapter (for multimodal OCR in syllabus_parser) ──

class _GenAIModelCompat:
    """
    Adapter allowing legacy code expecting a GenerativeModel interface
    to run transparently on the modern google.genai Client.
    """

    def __init__(self, client: genai.Client, model_name: str, config: types.GenerateContentConfig):
        self.client = client
        self.model_name = model_name
        self.config = config

    def generate_content(self, contents: Any, **kwargs):
        # Convert legacy dict parts (e.g. {"mime_type": ..., "data": bytes}) to types.Part
        converted_contents = []
        if isinstance(contents, list):
            for c in contents:
                if isinstance(c, dict) and "data" in c and "mime_type" in c:
                    converted_contents.append(
                        types.Part.from_bytes(data=c["data"], mime_type=c["mime_type"])
                    )
                else:
                    converted_contents.append(c)
        else:
            converted_contents = contents

        return self.client.models.generate_content(
            model=self.model_name,
            contents=converted_contents,
            config=self.config,
        )


def _init_model(
    temperature: float = 0.7,
    json_mode: bool = False,
    max_tokens: int = 4096,
    tools: Optional[List[Any]] = None,
    system_prompt: Optional[str] = None,
    preferred_model: Optional[str] = None,
) -> _GenAIModelCompat:
    """
    Backward-compatibility shim for core/syllabus_parser.py and legacy calls.
    Returns a _GenAIModelCompat wrapper powered by google.genai.
    """
    client = get_genai_client()
    config = types.GenerateContentConfig(
        temperature=temperature,
        top_p=0.9,
        top_k=32,
        max_output_tokens=max_tokens,
        response_mime_type="application/json" if json_mode else None,
        tools=tools,
        system_instruction=system_prompt,
    )
    model_name = preferred_model or GEMINI_MODEL
    return _GenAIModelCompat(client, model_name, config)
