"""
Centralized model configuration for OpenAgent.
This module provides a single source of truth for LLM configuration across all agents.
"""
from dotenv import load_dotenv
import os

# Load .env from project root (works for local development and LangGraph Server)
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.join(_CURRENT_DIR, "../..")
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI

# Cache for model instances to avoid recreating them
_model_cache = {}

def get_model(temperature: float = 0.2):
    """
    Get the configured DeepSeek model instance (text-only).

    Args:
        temperature: Controls randomness in generation (0.0 = deterministic, 1.0 = creative)

    Returns:
        ChatHuggingFace: Configured model instance ready for use

    Note:
        This model does NOT support vision/images. Use get_vision_model() for multimodal tasks.
    """
    # Use cached instance if available
    cache_key = f"deepseek_{temperature}"
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    llm = HuggingFaceEndpoint(
        repo_id="deepseek-ai/DeepSeek-V3.2",
        task="text-generation",
        do_sample=False,
        provider='novita',
        temperature=temperature,
    )

    model = ChatHuggingFace(llm=llm)
    # Add profile information for SummarizationMiddleware
    model.profile = {"max_input_tokens": 64000}

    _model_cache[cache_key] = model
    return model


def get_vision_model(temperature: float = 0.2):
    """
    Get a vision-capable model for multimodal tasks (text + images).

    Args:
        temperature: Controls randomness in generation (0.0 = deterministic, 1.0 = creative)

    Returns:
        ChatHuggingFace: Configured vision model instance

    Example:
        >>> from langchain_core.messages import HumanMessage
        >>> model = get_vision_model()
        >>> message = HumanMessage(content=[
        ...     {"type": "text", "text": "What's in this image?"},
        ...     {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        ... ])
        >>> response = model.invoke([message])
    """
    # Using Qwen-VL as vision model via HuggingFace
    # Configurar modelo via HuggingFace Router
    llm = HuggingFaceEndpoint(
        model="Qwen/Qwen3-Coder-Next",
        task="text-generation",
        do_sample=False,
        provider='novita',
        temperature=temperature,
        max_new_tokens=65536
    )
    model = ChatHuggingFace(
        llm=llm,
    )

    # Add profile information for SummarizationMiddleware
    model.profile = {"max_input_tokens": 262144}

    return model


# Default model instance for backward compatibility
from langchain_azure_ai.chat_models import AzureChatOpenAI
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(
    model="claude-opus-4-6",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url=os.getenv("AZURE_OPENAI_ENDPOINT")+"anthropic",
    temperature=0.3
)

if __name__ == "__main__":
    res = model.invoke("Olá!")
    print(res.content)