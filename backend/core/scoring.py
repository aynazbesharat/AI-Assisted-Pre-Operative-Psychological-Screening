def compute_scores(responses: list[dict]) -> dict:
    """
    responses: [{"id": 1, "value": 7}, {"id": 2, "value": "yes"}]
    """
    scores = {
        "anxiety_now": None,
        "info_need": None,
    }
    for r in responses:
        if r.get("id") == 1:
            scores["anxiety_now"] = int(r.get("value"))
        elif r.get("id") == 2:
            v = str(r.get("value")).lower().strip()
            scores["info_need"] = 1 if v in ["yes", "y", "true", "1"] else 0
    return scores


def compute_risk_band(scores: dict) -> tuple[str, list[str]]:
    # خیلی ساده (فعلاً): بر اساس اضطراب الان
    a = scores.get("anxiety_now")
    flags = []

    if a is None:
        return "unknown", ["missing_anxiety_score"]

    if a <= 3:
        band = "green"
    elif a <= 6:
        band = "yellow"
    elif a <= 8:
        band = "orange"
    else:
        band = "red"
        flags.append("high_anxiety_now")

    if scores.get("info_need") == 1:
        flags.append("needs_more_information")

    return band, flags
