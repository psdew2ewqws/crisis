import json
from typing import TypeVar
from pydantic import BaseModel, ValidationError
from app.llm.client import build_chat

T = TypeVar("T", bound=BaseModel)


def ask_json(system: str, user: str, schema: type[T]) -> T | None:
    """Call gemma in JSON mode, parse & validate against `schema`.
    Returns None on any failure so callers can fall back to engine output."""
    llm = build_chat(json_mode=True)
    msg = llm.invoke([("system", system), ("human", user)])
    try:
        data = json.loads(str(msg.content))
        return schema.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return None
