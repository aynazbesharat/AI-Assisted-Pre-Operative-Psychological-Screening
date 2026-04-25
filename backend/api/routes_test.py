from fastapi import APIRouter

from schemas.models import QuestionnaireItem
from question_engine.local_question_generator import generate_local_questions

router = APIRouter(prefix="/api", tags=["test"])

#@router.get("/test/questionnaire", response_model=list[QuestionnaireItem])
#def get_test_questionnaire():
    # Always return the same questionnaire used by /api/questionnaire and /api/submit
    #return generate_local_questions()
