from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func

from db import Base


class Report(Base):
    __tablename__ = "psychological_screening_reports"

    id = Column(Integer, primary_key=True, index=True)
    mrn = Column(String(32), nullable=False, index=True)
    surgery = Column(String(255), nullable=True)

    questionnaire_id = Column(String(64), nullable=False, index=True)

    ai_risk_color = Column(String(16), nullable=False)
    ai_risk_percent = Column(Float, nullable=False)

    anxiety_score = Column(Integer, nullable=False, default=0)
    mood_score = Column(Integer, nullable=False, default=0)
    info_score = Column(Integer, nullable=False, default=0)
    coping_score = Column(Integer, nullable=False, default=0)
    safety_score = Column(Integer, nullable=False, default=0)

    ai_scores_json = Column(Text, nullable=False)
    ai_explanation = Column(Text, nullable=False)
    ai_key_signals_json = Column(Text, nullable=False)

    model = Column(String(64), nullable=False)
    prompt_version = Column(String(64), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)