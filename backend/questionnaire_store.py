import uuid

_STORE = {}

def create_questionnaire(questions):
    qid = str(uuid.uuid4())
    _STORE[qid] = questions
    return qid

def get_questionnaire(qid):
    return _STORE.get(qid)
