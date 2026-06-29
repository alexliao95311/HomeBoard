import httpx

from app.ai.providers.base import AIProvider

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 90.0


class OpenRouterProvider(AIProvider):
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        self._api_key = api_key

    def complete(self, messages: list[dict], model: str) -> str:
        try:
            response = httpx.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "messages": messages},
                timeout=_TIMEOUT,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(
                f"OpenRouter returned {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise AIProviderError("OpenRouter request timed out") from exc
        except httpx.NetworkError as exc:
            raise AIProviderError(f"Network error reaching OpenRouter: {exc}") from exc

        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AIProviderError(
                f"Unexpected OpenRouter response shape: {response.text[:200]}"
            ) from exc


class AIProviderError(Exception):
    """Raised when the AI provider call fails."""
