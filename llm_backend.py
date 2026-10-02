"""Text-only LLM backend for the moment picker: any OpenAI-compatible server.

Ollama, LM Studio, vLLM, llama.cpp's server, LocalAI and OpenRouter all speak
``POST {base}/chat/completions``. When ``LLM_BASE_URL`` is set (or
``LLM_PROVIDER=openai``), the transcript scoring and detail passes in
``main.get_viral_clips`` go here instead of Gemini, so a self-hosted install
can run the whole pipeline without a Google key.

Frame-based stages use ``local_vision.py`` when Ollama/Qwen is configured.
Gemini remains an optional upstream-compatible fallback, never a requirement
for the MAPA ROTO desktop build.

Structured output: the prompts already spell out the exact JSON shape, so a
plain ``json_object`` mode is enough for most models. The request first asks
for ``json_schema`` (Ollama, vLLM, llama.cpp and LM Studio enforce it); a
server that rejects that field gets the same request again with
``json_object``, then with no ``response_format`` at all. Whatever comes back
is validated with the same pydantic model Gemini's ``response_schema`` uses,
so ``main.py`` sees one shape regardless of provider.
"""
from __future__ import annotations

import json
import os
from typing import Optional, Tuple, Type

import httpx
from pydantic import BaseModel

DEFAULT_MODEL = "qwen3.5:4b"
DEFAULT_TIMEOUT = 600.0  # local models on CPU are slow; a scoring batch can take minutes


def provider() -> str:
    """``"openai"`` when a compatible endpoint is configured, else ``"gemini"``."""
    explicit = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if explicit in ("openai", "ollama", "local", "openai-compatible"):
        return "openai"
    if explicit == "gemini":
        return "gemini"
    return "openai" if base_url() else "gemini"


def is_ollama() -> bool:
    """Whether the configured OpenAI-compatible endpoint is Ollama itself.

    The desktop build always sets ``LLM_PROVIDER=ollama``.  Keeping this
    explicit matters because Ollama's native ``/api/chat`` endpoint accepts a
    JSON schema directly and separates thinking from the final answer.  That
    path is more deterministic for small Qwen models than emulating OpenAI's
    ``response_format`` negotiation.
    """
    explicit = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if explicit == "ollama":
        return True
    return bool((os.environ.get("OLLAMA_BASE_URL") or "").strip())


def base_url() -> str:
    return (os.environ.get("LLM_BASE_URL") or "").strip().rstrip("/")


def model_name() -> str:
    return (os.environ.get("LLM_MODEL") or "").strip() or DEFAULT_MODEL


def active() -> bool:
    """True when the moment picker should call the OpenAI-compatible server."""
    return provider() == "openai" and bool(base_url())


def describe() -> Optional[dict]:
    """What ``/api/config`` tells the dashboard, or ``None`` when inactive."""
    if not active():
        return None
    return {"provider": "openai", "model": model_name(), "baseUrl": base_url()}


def _timeout() -> float:
    try:
        return float(os.environ.get("LLM_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        return DEFAULT_TIMEOUT


def _headers() -> dict:
    # Ollama ignores the key but the OpenAI client convention (and vLLM with
    # --api-key) wants the header present; "ollama" is the documented placeholder.
    key = (os.environ.get("LLM_API_KEY") or "ollama").strip()
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _client(**kwargs) -> httpx.Client:
    """Factory so tests can swap in ``httpx.MockTransport``."""
    return httpx.Client(timeout=_timeout(), **kwargs)


def _ollama_base_url() -> str:
    explicit = (os.environ.get("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    configured = base_url()
    return configured[:-3] if configured.endswith("/v1") else configured


def _ollama_generate_json(prompt: str, schema: Type[BaseModel], model: str,
                          ) -> Tuple[dict, Optional[dict]]:
    """Structured output through Ollama's native API.

    ``think=False`` keeps Qwen's reasoning tokens out of the JSON response.
    Older Ollama builds that reject that field are retried once without it;
    the JSON schema remains enforced in both attempts.
    """
    schema_json = schema.model_json_schema()
    grounded_prompt = (
        prompt
        + "\n\nReturn exactly one JSON object matching this schema:\n"
        + json.dumps(schema_json, ensure_ascii=False, separators=(",", ":"))
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Answer with the requested JSON object only."},
            {"role": "user", "content": grounded_prompt},
        ],
        "format": schema_json,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_ctx": 8192},
    }
    url = f"{_ollama_base_url()}/api/chat"
    with _client() as client:
        response = client.post(url, json=body, headers={"Content-Type": "application/json"})
        if response.status_code in (400, 422) and "think" in response.text.lower():
            body.pop("think", None)
            response = client.post(url, json=body, headers={"Content-Type": "application/json"})
    if response.status_code >= 400:
        raise RuntimeError(
            f"Ollama server {response.status_code} from {url}: {response.text[:300]}")

    data = response.json()
    message = data.get("message") or {}
    text = message.get("content") or ""
    if not str(text).strip():
        reason = data.get("done_reason") or "empty content"
        raise RuntimeError(f"Ollama returned no final JSON ({reason})")
    import gemini_worker
    parsed = gemini_worker._parse_json_response_text(str(text))
    validated = schema.model_validate(parsed).model_dump()
    return validated, {
        "input_tokens": int(data.get("prompt_eval_count") or 0),
        "output_tokens": int(data.get("eval_count") or 0),
        "thinking_tokens": 0,
        "input_cost": 0.0,
        "output_cost": 0.0,
        "total_cost": 0.0,
        "model": model,
        "price_estimated": False,
        "local": True,
    }


def _response_formats(schema: Type[BaseModel]):
    name = getattr(schema, "__name__", "response").lower()
    yield {"type": "json_schema",
           "json_schema": {"name": name, "schema": schema.model_json_schema()}}
    yield {"type": "json_object"}
    yield None


def _is_format_rejection(resp: httpx.Response) -> bool:
    if resp.status_code not in (400, 422):
        return False
    body = resp.text.lower()
    return "response_format" in body or "json_schema" in body or "json_object" in body \
        or "format" in body


def generate_json(prompt: str, schema: Type[BaseModel], model: Optional[str] = None,
                  ) -> Tuple[dict, Optional[dict]]:
    """One chat completion that must come back as JSON matching ``schema``.

    Returns ``(parsed_dict, cost_analysis)`` in the exact shape
    ``main._run_gemini_stage`` returns, so the caller does not branch on the
    provider. Raises on HTTP errors, empty bodies and schema violations; the
    retry policy lives in the caller, same as for Gemini.
    """
    import gemini_worker  # local import: keeps this module free of the google SDK

    model = model or model_name()
    if is_ollama():
        return _ollama_generate_json(prompt, schema, model)

    url = f"{base_url()}/chat/completions"
    messages = [
        {"role": "system", "content": "You answer with a single JSON object and nothing else."},
        {"role": "user", "content": prompt},
    ]
    last_rejection: Optional[str] = None
    with _client() as client:
        for fmt in _response_formats(schema):
            body = {"model": model, "messages": messages, "temperature": 0.2, "stream": False}
            if fmt is not None:
                body["response_format"] = fmt
            resp = client.post(url, json=body, headers=_headers())
            if fmt is not None and _is_format_rejection(resp):
                # The server does not know this response_format flavour; the
                # next loop iteration asks for a looser one.
                last_rejection = resp.text[:200]
                continue
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"LLM server {resp.status_code} from {url}: {resp.text[:300]}")
            data = resp.json()
            break
        else:
            raise RuntimeError(
                f"LLM server rejected every response_format variant: {last_rejection}")

    choices = data.get("choices") or []
    text = ""
    if choices:
        msg = choices[0].get("message") or {}
        text = msg.get("content") or ""
        if isinstance(text, list):  # some servers return content parts
            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
    parsed = gemini_worker._parse_json_response_text(text)
    # Validate against the same schema Gemini enforces server-side, so a
    # local model that drops a field fails here with a readable error
    # (retried by the caller) instead of deep inside the clip pipeline.
    validated = schema.model_validate(parsed).model_dump()

    usage = data.get("usage") or {}
    cost = {
        "input_tokens": int(usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("completion_tokens") or 0),
        "thinking_tokens": 0,
        "input_cost": 0.0,
        "output_cost": 0.0,
        "total_cost": 0.0,
        "model": model,
        "price_estimated": False,
        "local": True,
    }
    return validated, cost
