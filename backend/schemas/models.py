from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal

RiskBand = Literal["green", "yellow", "orange", "red"]

class QuestionnaireItem(BaseModel):
    id: int
    question: str
    type: str
    min: Optional[int] = None
    max: Optional[int] = None

class SubmitTestRequest(BaseModel):
    session_id: str = Field(..., description="Unique session for this test run")
    theory: str = Field("CBT", description="Selected theory label")
    answers: Dict[str, Any] = Field(default_factory=dict)

class ScoresPayload(BaseModel):
    scores: Dict[str, float] = Field(default_factory=dict)
    risk_band: RiskBand = "yellow"
    flags: List[str] = Field(default_factory=list)

class SubmitTestResponse(BaseModel):
    session_id: str
    theory: str
    result: ScoresPayload
    ai_allowed_payload: Dict[str, Any] = Field(default_factory=dict)

class AIChatRequest(BaseModel):
    session_id: str
    message: str
    theory: str = "CBT"
    result: ScoresPayload

class AIChatResponse(BaseModel):
    session_id: str
    assistant_message: str
