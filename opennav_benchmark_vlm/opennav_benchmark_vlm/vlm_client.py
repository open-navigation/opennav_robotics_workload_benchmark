from openai import OpenAI


class VLMClient:
    """Thin wrapper around the OpenAI Chat Completions wire format.

    The `openai` Python package is just a typed HTTP client — pointing
    `base_url` at a local server (llama.cpp / vLLM / Ollama) keeps all
    traffic on loopback.
    """

    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float, max_tokens: int):
        """Configure the HTTP client; nothing is sent until `chat` is called."""
        self._client = OpenAI(base_url=base_url, api_key=api_key or 'EMPTY')
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def chat(self, messages, timeout: float) -> str:
        """Send a chat-completions request and return the assistant's text content (empty string if missing)."""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            timeout=timeout,
        )
        return resp.choices[0].message.content or ''
