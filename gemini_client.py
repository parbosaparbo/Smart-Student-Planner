"""
StudyMind AI — Gemini API Client with MCP Tool Calling & Strict JSON Enforcement
"""
import functools
import json
import logging
import os
import re
from typing import Any, Callable, Dict, Generator, List, Optional, Union

import google.generativeai as genai
from config import GEMINI_API_KEY as DEFAULT_KEY, GEMINI_MODEL

logger = logging.getLogger("StudyMind.GeminiClient")

# Model fallback chain in case the primary model is rate-limited or deprecated
FALLBACK_MODELS = [
    GEMINI_MODEL,
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-flash-latest",
]


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
            return st.session_state["gemini_api_key"].strip()
    except Exception:
        pass
    env_k = os.getenv("GEMINI_API_KEY", "").strip()
    if env_k:
        return env_k
    return (DEFAULT_KEY or "").strip()


def _init_model(
    temperature: float = 0.7,
    json_mode: bool = False,
    max_tokens: int = 4096,
    tools: Optional[List[Any]] = None,
    system_prompt: Optional[str] = None,
    preferred_model: Optional[str] = None,
):
    """
    Initialize and return a Gemini model instance with automatic model fallback
    if quota is exhausted on the primary model.
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set. Enter your key in the sidebar or add it to .env.")

    genai.configure(api_key=api_key)
    config_dict = {
        "temperature": temperature,
        "top_p": 0.9,
        "top_k": 32,
        "max_output_tokens": max_tokens,
    }
    if json_mode:
        config_dict["response_mime_type"] = "application/json"

    generation_config = genai.GenerationConfig(**config_dict)

    model_to_use = preferred_model or GEMINI_MODEL
    return genai.GenerativeModel(
        model_name=model_to_use,
        generation_config=generation_config,
        tools=tools,
        system_instruction=system_prompt,
    )


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
    # Remove trailing unclosed key or partial value
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
    Executes a Gemini call against primary model and automatically falls back to secondary models
    if 429 RESOURCE_EXHAUSTED or 404 NOT_FOUND occurs.
    """
    last_error = None
    for model_name in FALLBACK_MODELS:
        try:
            return generate_fn(model_name)
        except Exception as e:
            err_msg = str(e)
            if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg or "404" in err_msg or "NOT_FOUND" in err_msg:
                logger.warning(f"Model '{model_name}' hit rate limit/unavailable. Trying next model... ({err_msg[:80]})")
                last_error = e
                continue
            elif "API_KEY_INVALID" in err_msg or "400" in err_msg or "403" in err_msg:
                raise ValueError(
                    f"Gemini API Key Error: {err_msg}\n\n"
                    "💡 Please verify your API key at https://aistudio.google.com/ "
                    "(Google AI Studio keys typically begin with 'AIzaSy...')."
                )
            raise e
    raise last_error or RuntimeError("All Gemini fallback models exhausted.")


@_safe_cache
def call_gemini_json(prompt: str, temperature: float = 0.3, max_tokens: int = 4096) -> dict:
    """
    Call Gemini in native constrained JSON mode with automatic model fallback.
    """
    def _call(model_name: str):
        model = _init_model(temperature=temperature, json_mode=True, max_tokens=max_tokens, preferred_model=model_name)
        response = model.generate_content(prompt)
        raw = response.text
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
def call_gemini_text(prompt: str, temperature: float = 0.8) -> str:
    """
    Call Gemini and return plain text (for chatbot, briefing, onboarding).
    """
    def _call(model_name: str):
        model = _init_model(temperature=temperature, preferred_model=model_name)
        response = model.generate_content(prompt)
        return response.text

    return _execute_with_model_fallback(_call)


def call_gemini_chat(messages: list, system_prompt: str = "", temperature: float = 0.8) -> str:
    """
    Multi-turn chat call. messages = [{"role": "user"|"model", "content": "..."}]
    """
    def _call(model_name: str):
        api_key = get_api_key()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.GenerationConfig(temperature=temperature, max_output_tokens=8192),
            system_instruction=system_prompt if system_prompt else None,
        )

        history = []
        for m in messages[:-1]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})

        chat = model.start_chat(history=history)
        last_msg = messages[-1]["content"] if messages else ""
        response = chat.send_message(last_msg)
        return response.text

    return _execute_with_model_fallback(_call)


def call_gemini_stream(prompt: str, temperature: float = 0.8) -> Generator[str, None, None]:
    """
    Call Gemini with stream=True. Yields text chunks live as they arrive.
    Compatible with Streamlit's st.write_stream().
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    def _call(model_name: str):
        model = _init_model(temperature=temperature, preferred_model=model_name)
        return model.generate_content(prompt, stream=True)

    stream_resp = _execute_with_model_fallback(_call)
    for chunk in stream_resp:
        if chunk.text:
            yield chunk.text


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

    def _call(model_name: str):
        model = _init_model(
            temperature=temperature,
            tools=tools if tools else None,
            system_prompt=system_prompt,
            preferred_model=model_name,
        )
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(prompt)
        return response.text

    return _execute_with_model_fallback(_call)
