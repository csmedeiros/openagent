from langchain.agents.middleware.summarization import DEFAULT_SUMMARY_PROMPT
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState
from langchain_core.messages.utils import count_tokens_approximately

# Trigger de tokens para sumarização
SUMMARIZATION_TOKEN_TRIGGER = 30000
# Tokens a preservar após sumarização
TOKENS_TO_KEEP = 5000

# Import centralized model configuration
from agents.models import get_model

model = get_model(temperature=0.2)



def should_summarize(state: MessagesState) -> str:
    """
    Conditional edge para LangGraph que verifica se deve resumir mensagens.

    Retorna 'summarize' se o número de tokens exceder o trigger,
    caso contrário retorna 'agent' para prosseguir diretamente.

    Args:
        state: Estado do MessagesState contendo as mensagens

    Returns:
        'summarize' se deve resumir, 'agent' caso contrário
    """
    messages = state.get("messages", [])

    if not messages:
        return "agent"

    # Conta tokens aproximadamente
    total_tokens = count_tokens_approximately(messages)

    if total_tokens >= SUMMARIZATION_TOKEN_TRIGGER:
        return "summarize"

    return "agent"


def summarize_messages_node(state: MessagesState) -> dict:
    """
    Nó do LangGraph que resume mensagens quando o trigger é atingido.

    Funciona como o SummarizationMiddleware, extraindo o contexto mais relevante
    das mensagens para liberar espaço no histórico da conversa.

    Args:
        state: Estado do MessagesState contendo as mensagens

    Returns:
        Dicionário com as novas mensagens (resumo + mensagens recentes preservadas)
    """
    messages = state.get("messages", [])

    if not messages:
        return {"messages": []}

    # Verifica se as mensagens já cabem no limite de tokens
    total_tokens = count_tokens_approximately(messages)
    if total_tokens <= TOKENS_TO_KEEP:
        return {"messages": messages}

    # Encontra o ponto de corte para preservar aproximadamente TOKENS_TO_KEEP tokens
    # Itera de trás para frente acumulando tokens até atingir o limite
    cutoff_index = len(messages)
    accumulated_tokens = 0

    for i in range(len(messages) - 1, -1, -1):
        msg_tokens = count_tokens_approximately([messages[i]])

        if accumulated_tokens + msg_tokens <= TOKENS_TO_KEEP:
            accumulated_tokens += msg_tokens
            cutoff_index = i
        else:
            # Atingimos o limite de tokens
            break

    # Garante que pelo menos 1 mensagem seja preservada
    if cutoff_index >= len(messages):
        cutoff_index = len(messages) - 1

    # Garante que haja mensagens para resumir
    if cutoff_index == 0:
        # Todas as mensagens serão preservadas (situação improvável)
        return {"messages": messages}

    # Particiona mensagens: antigas para resumir e recentes para preservar
    messages_to_summarize = messages[:cutoff_index]
    preserved_messages = messages[cutoff_index:]

    # Formata as mensagens antigas para sumarização
    formatted_messages = "\n".join([
        f"{msg.__class__.__name__}: {msg.content}"
        for msg in messages_to_summarize
    ])

    try:
        # Invoca o modelo com o prompt de sumarização
        response = model.invoke(DEFAULT_SUMMARY_PROMPT.format(messages=formatted_messages))
        summary_text = response.content.strip()

        # Cria mensagem de resumo
        summary_message = SystemMessage(
            content=f"Here is a summary of the conversation to date:\n\n{summary_text}"
        )

        # Retorna resumo + mensagens preservadas
        return {"messages": [summary_message] + preserved_messages}

    except Exception as e:
        # Em caso de erro, mantém as mensagens originais
        print(f"Error generating summary: {e!s}")
        return {"messages": messages}
