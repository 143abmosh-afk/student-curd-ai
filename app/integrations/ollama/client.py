import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT_SECONDS = 120


class OllamaUnavailableError(Exception):
    pass


class OllamaResponseError(Exception):
    pass


def generate(prompt: str) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", OLLAMA_BASE_URL).rstrip("/")
    model = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)
    request_body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    request = Request(
        f"{base_url}/api/chat",
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise OllamaUnavailableError(
            "The local Ollama service is unavailable."
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise OllamaResponseError(
            "The local Ollama service returned an invalid response."
        ) from exc

    try:
        content = payload["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise OllamaResponseError(
            "The local Ollama service returned an invalid response."
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise OllamaResponseError(
            "The local Ollama service returned an empty response."
        )
    return content
