from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

# configure_azure_monitor(connection_string=)
# OpenAIInstrumentor().instrument()

from langchain_azure_ai.callbacks.tracers import AzureAIOpenTelemetryTracer
import os
from dotenv import load_dotenv
load_dotenv()

callback = AzureAIOpenTelemetryTracer(connection_string=os.getenv("AZURE_TRACING_CONNECTION_STRING"))
