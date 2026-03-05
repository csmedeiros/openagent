import sys
import traceback
from langchain.chat_models import init_chat_model

with open("test_out.txt", "w") as f:
    try:
        model = init_chat_model(
            model="claude-sonnet-4-5",
            model_provider="anthropic",
            api_key="fake-key",
            base_url="https://fake-url.com"
        )
        f.write(f"Success: {type(model)}\n")
        f.write(f"API Key in model: {getattr(model, 'anthropic_api_key', 'Not Found')}\n")
        f.write(f"Base URL in model: {getattr(model, 'anthropic_api_url', 'Not Found')}\n")
    except Exception as e:
        f.write(f"Error: {str(e)}\n")
        f.write(traceback.format_exc())
