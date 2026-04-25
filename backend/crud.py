# backend/crud.py
import json
from sqlalchemy.orm import Session
from models import Report


def save_report(
    db: Session,
    mrn: str,
    surgery: str,
    questionnaire_id: str,
    ai_scores: dict,
    ai_risk_color: str,
    ai_risk_percent: float,
    ai_explanation: str,
    ai_key_signals: list,
    model: str,
    prompt_version: str,
):
    report = Report(
        mrn=mrn,
        surgery=surgery,
        questionnaire_id=questionnaire_id,
        ai_scores_json=json.dumps(ai_scores),
        ai_risk_color=ai_risk_color,
        ai_risk_percent=ai_risk_percent,
        ai_explanation=ai_explanation,
        ai_key_signals_json=json.dumps(ai_key_signals),
        model=model,
        prompt_version=prompt_version,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report