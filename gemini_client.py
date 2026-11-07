"""
StudyMind AI — Gemini API client with strict JSON enforcement
"""
import json
import re
import os
import google.generativeai as genai
from config import GEMINI_API_KEY as DEFAULT_KEY, GEMINI_MODEL


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


def _init_model(temperature: float = 0.7, json_mode: bool = False):
    """Initialize and return a Gemini model instance."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set. Enter your key in the sidebar or add it to .env.")
    
    genai.configure(api_key=api_key)
    generation_config = genai.GenerationConfig(
        temperature=temperature,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
    )
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config=generation_config,
    )


def _strip_to_json(text: str) -> str:
    """
    Strip any markdown wrappers and extract raw JSON.
    Handles: ```json ... ```, ``` ... ```, or plain text with leading/trailing noise.
    """
    # Remove ```json ... ``` or ``` ... ``` wrappers
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    text = text.strip()

    # Find the first { and last } to extract JSON
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    # Try array
    start = text.find("[")
    end   = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def call_gemini_json(prompt: str, temperature: float = 0.4) -> dict:
    """
    Call Gemini and return a parsed JSON dict.
    Uses low temperature for structured outputs.
    Raises ValueError if response is not valid JSON.
    """
    model = _init_model(temperature=temperature)
    try:
        response = model.generate_content(prompt)
        raw = response.text
    except Exception as e:
        # If model quota or error, provide clean feedback
        raise ValueError(f"Gemini API error: {e}")

    cleaned = _strip_to_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Gemini returned invalid JSON.\n\nRaw response:\n{raw}\n\nError: {e}"
        )


def call_gemini_text(prompt: str, temperature: float = 0.8) -> str:
    """
    Call Gemini and return plain text (for chatbot, briefing, onboarding).
    Uses higher temperature for natural conversation.
    """
    model = _init_model(temperature=temperature)
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise ValueError(f"Gemini API error: {e}")


def call_gemini_chat(messages: list, system_prompt: str = "", temperature: float = 0.8) -> str:
    """
    Multi-turn chat call. messages = [{"role": "user"|"model", "content": "..."}]
    """
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
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
