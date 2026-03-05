"""
Centralized model configuration for OpenAgent.

LLM provider is configured via environment variables (or the Settings UI):

  MODEL_PROVIDER   - LangChain provider name, e.g. openai, anthropic, groq,
                     huggingface_endpoint, azure_openai.  Default: anthropic
  MODEL_NAME       - Model/deployment name.  Default: claude-opus-4-6
  MODEL_API_KEY    - API key for the provider.  Falls back to provider-specific
                     env vars (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
  MODEL_BASE_URL   - Optional custom base URL (useful for proxies / Azure).

All variables can be updated at runtime via the API's POST /settings endpoint
without restarting the server.
"""

from dotenv import load_dotenv
import os

# Load .env from project root
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.join(_CURRENT_DIR, "../../..")
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from langchain.chat_models import init_chat_model  # LangChain ≥ 0.3

# ─── Model cache ──────────────────────────────────────────────────────────────
# Keyed by (provider, name, base_url, temperature) to avoid recreating identical
# instances.  Call clear_model_cache() after a settings change.
_model_cache: dict = {}


def _build_kwargs(temperature: float, base_url: str | None, api_key: str | None) -> dict:
    kwargs: dict = {"temperature": temperature}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    return kwargs


def get_model(temperature: float = 0.2):
    """
    Return the configured chat model for the agent.

    Provider / model / credentials are read from environment variables so they
    can be changed at runtime via the Settings UI without restarting the server.
    """
    provider  = os.environ.get("MODEL_PROVIDER", "anthropic")
    name      = os.environ.get("MODEL_NAME",     "claude-opus-4-6")
    api_key   = os.environ.get("MODEL_API_KEY")
    base_url  = os.environ.get("MODEL_BASE_URL")

    cache_key = (provider, name, base_url, temperature)
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    kwargs = _build_kwargs(temperature, base_url, api_key)
    instance = init_chat_model(model=name, model_provider=provider, **kwargs)

    _model_cache[cache_key] = instance
    return instance


def get_vision_model(temperature: float = 0.2):
    """
    Return a vision-capable model.

    Falls back to MODEL_VISION_NAME / get_model() if no dedicated vision model
    is configured.
    """
    provider  = os.environ.get("MODEL_PROVIDER", "anthropic")
    name      = os.environ.get("MODEL_VISION_NAME",
                               os.environ.get("MODEL_NAME", "claude-opus-4-6"))
    api_key   = os.environ.get("MODEL_API_KEY")
    base_url  = os.environ.get("MODEL_BASE_URL")

    cache_key = (f"vision_{provider}", name, base_url, temperature)
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    kwargs = _build_kwargs(temperature, base_url, api_key)
    instance = init_chat_model(model=name, model_provider=provider, **kwargs)

    _model_cache[cache_key] = instance
    return instance


def clear_model_cache():
    """Invalidate the model cache.  Call this after updating env vars."""
    _model_cache.clear()


# ─── Default model instance (backward compat) ────────────────────────────────
# Created lazily so env vars set after import are respected.
class _LazyModel:
    """Proxy that forwards attribute access to the real model on first use."""

    _instance = None

    def _get(self):
        if self._instance is None:
            self._instance = get_model()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)

    def __call__(self, *args, **kwargs):
        return self._get()(*args, **kwargs)

    def invoke(self, *args, **kwargs):
        return self._get().invoke(*args, **kwargs)

    def bind_tools(self, *args, **kwargs):
        return self._get().bind_tools(*args, **kwargs)

    def ainvoke(self, *args, **kwargs):
        return self._get().ainvoke(*args, **kwargs)


model = _LazyModel()


if __name__ == "__main__":
    res = get_model().invoke("Olá!")
    print(res.content)