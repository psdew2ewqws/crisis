from functools import lru_cache
from langchain_ollama import ChatOllama, OllamaEmbeddings
from app.core.config import get_settings


@lru_cache
def build_chat(json_mode: bool = False) -> ChatOllama:
    s = get_settings()
    return ChatOllama(
        model=s.OLLAMA_CHAT_MODEL,
        base_url=s.OLLAMA_BASE_URL,
        temperature=0.2,
        format="json" if json_mode else "",
    )


@lru_cache
def build_embeddings() -> OllamaEmbeddings:
    s = get_settings()
    return OllamaEmbeddings(model=s.OLLAMA_EMBED_MODEL, base_url=s.OLLAMA_BASE_URL)
