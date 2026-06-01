from pydantic import BaseModel, Field


class CaseState(BaseModel):
    case_id: str
    step: str = "init"
    signals: list[dict] = Field(default_factory=list)
    incident: dict | None = None
    root_cause: dict | None = None
    risk: dict | None = None
    solutions: list[dict] = Field(default_factory=list)
    sim: dict | None = None
    recommendation: dict | None = None
    decision: dict | None = None
    trace: list[dict] = Field(default_factory=list)
    error: str | None = None
