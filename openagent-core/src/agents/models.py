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

def get_model(temperature: float = 0.2):
    """
    Return the configured chat model for the agent.

    Provider / model / credentials are read from environment variables so they
    can be changed at runtime via the Settings UI without restarting the server.
    """

    llm = init_chat_model(model="claude-sonnet-4-6", model_provider="anthropic", base_url=os.getenv("ANTHROPIC_FOUNDRY_BASE_URL"), api_key=os.getenv("ANTHROPIC_FOUNDRY_API_KEY"), temperature=temperature)
    return llm

def get_vision_model(temperature: float = 0.2):
    """
    Return a vision-capable model.
    """
    llm = init_chat_model(
        model="claude-sonnet-4-6",
        model_provider="anthropic",
        base_url=os.getenv("ANTHROPIC_FOUNDRY_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_FOUNDRY_API_KEY"),
        temperature=temperature
    )
    return llm


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