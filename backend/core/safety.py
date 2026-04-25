from fastapi import HTTPException


def _extract_value(r):
    """Accept either a raw value (int/str/bool) or a dict like {value: ...} / {answer: ...}."""
    if isinstance(r, dict):
        if "value" in r:
            return r["value"]
        if "answer" in r:
            return r["answer"]
    return r


def validate_responses(questionnaire, responses):
    """Validate user answers against the questionnaire.

    - questionnaire: list[dict] with keys: type, min/max (for scale)
    - responses: either list[int] OR list[dict] where each dict contains value/answer
    """

    if len(questionnaire) != len(responses):
        raise HTTPException(
            status_code=400,
            detail="Number of responses does not match number of questions",
        )

    for q, r_raw in zip(questionnaire, responses):
        qtype = q.get("type")
        r = _extract_value(r_raw)

        # Normalize numeric strings like "5" -> 5
        if isinstance(r, str) and r.strip().isdigit():
            r = int(r.strip())

        if qtype == "scale":
            # Reject bool (because bool is a subclass of int in Python)
            if isinstance(r, bool) or not isinstance(r, int):
                raise HTTPException(status_code=400, detail="Scale answer must be integer")

            qmin = q.get("min")
            qmax = q.get("max")
            if qmin is not None and r < qmin:
                raise HTTPException(status_code=400, detail="Scale answer out of range")
            if qmax is not None and r > qmax:
                raise HTTPException(status_code=400, detail="Scale answer out of range")

        elif qtype == "yes_no":
            # Allow 0/1 ints only (or "0"/"1" after normalization)
            if isinstance(r, bool) or not isinstance(r, int) or r not in (0, 1):
                raise HTTPException(status_code=400, detail="Yes/No answer must be 0 or 1")

        else:
            raise HTTPException(status_code=400, detail=f"Unknown question type: {qtype}")
