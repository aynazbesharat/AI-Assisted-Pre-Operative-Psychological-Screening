import io
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Literal, Tuple

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError, model_validator

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from db import SessionLocal
from crud import save_report

router = APIRouter(prefix="/api", tags=["api"])
print("USING ROUTES FILE:", __file__)

Theory = Literal["CBT", "StressCoping", "InfoNeed", "Safety"]
RiskColor = Literal["green", "yellow", "orange", "red"]
QuestionScale = Literal[
    "intensity",
    "frequency",
    "agreement",
    "confidence",
    "clarity",
    "support",
]

DOMAIN_KEYS: Tuple[str, ...] = ("anxiety", "mood", "info", "coping", "safety")
DOMAIN_MIN = 0
DOMAIN_MAX = 16

PROMPT_VERSION = "openai_full_v2_scales"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_Q_STORE: Dict[str, List[Dict[str, Any]]] = {}

DISCLAIMER = (
    "Note: This is a non-diagnostic psychological screening explanation. "
    "It does not diagnose conditions or provide treatment decisions. "
    "For medical decisions, rely on your clinical team."
)

USED_THEORIES = ["CBT", "Stress & Coping", "Information-Need", "Psychological Safety"]

SCALE_LABELS: Dict[str, List[str]] = {
    "intensity": ["Not at all", "A little", "Moderately", "Quite a bit", "Extremely"],
    "frequency": ["Never", "Rarely", "Sometimes", "Often", "Very often"],
    "agreement": ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"],
    "confidence": [
        "Not at all confident",
        "Slightly confident",
        "Moderately confident",
        "Very confident",
        "Extremely confident",
    ],
    "clarity": [
        "Not at all clear",
        "Slightly clear",
        "Moderately clear",
        "Mostly clear",
        "Completely clear",
    ],
    "support": [
        "No support",
        "A little support",
        "Moderate support",
        "Strong support",
        "Very strong support",
    ],
}


class QuestionnaireItem(BaseModel):
    id: int
    text: str
    theory: Theory
    domain: Literal["anxiety", "mood", "info", "coping", "safety"]
    scale: QuestionScale = "intensity"


class QuestionnaireResponse(BaseModel):
    questionnaire_id: str
    questions: List[QuestionnaireItem]


class SubmitAnswer(BaseModel):
    question_id: int
    answer: int


class SubmitPayload(BaseModel):
    mrn: Optional[str] = None
    surgery: Optional[str] = None
    questionnaire_id: str
    responses: List[SubmitAnswer]


class OpenAIScoringResult(BaseModel):
    ai_scores: Dict[str, int]
    ai_risk_color: RiskColor
    ai_risk_percent: float
    ai_explanation: str
    ai_key_signals: List[str]
    ai_followup_questions: List[str]

    @model_validator(mode="after")
    def _validate_constraints(self):
        missing = [k for k in DOMAIN_KEYS if k not in self.ai_scores]
        extra = [k for k in self.ai_scores.keys() if k not in DOMAIN_KEYS]
        if missing:
            raise ValueError(f"ai_scores missing keys: {missing}")
        if extra:
            raise ValueError(f"ai_scores has unexpected keys: {extra}")

        for k in DOMAIN_KEYS:
            v = self.ai_scores[k]
            if not isinstance(v, int):
                raise ValueError(f"ai_scores['{k}'] must be int")
            if v < DOMAIN_MIN or v > DOMAIN_MAX:
                raise ValueError(f"ai_scores['{k}'] out of range {DOMAIN_MIN}..{DOMAIN_MAX}: {v}")

        if not (0.0 <= float(self.ai_risk_percent) <= 100.0):
            raise ValueError(f"ai_risk_percent out of range 0..100: {self.ai_risk_percent}")

        if not (3 <= len(self.ai_key_signals) <= 5):
            raise ValueError("ai_key_signals must have 3..5 items")
        if not (2 <= len(self.ai_followup_questions) <= 3):
            raise ValueError("ai_followup_questions must have 2..3 items")

        if not self.ai_explanation.strip():
            raise ValueError("ai_explanation must be non-empty")

        return self


class SubmitResponse(BaseModel):
    mrn: str
    surgery: Optional[str] = None
    questionnaire_id: str
    ai_scores: Dict[str, int]
    ai_risk_color: RiskColor
    ai_risk_percent: float
    ai_explanation: str
    ai_key_signals: List[str]
    ai_followup_questions: List[str]
    disclaimer: str
    used_theories: List[str]
    model: str
    prompt_version: str


class ContextItem(BaseModel):
    id: Optional[int] = None
    theory: Optional[Theory] = None
    question: str
    answer: Optional[int] = None
    scale: Optional[QuestionScale] = None


class AIChatRequest(BaseModel):
    mrn: Optional[str] = None
    surgery: Optional[str] = None
    message: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = None
    history: Optional[List[Dict[str, str]]] = None


class AIChatResponse(BaseModel):
    answer: str
    disclaimer: str
    used_theories: List[str]
    model: str
    prompt_version: str


class PDFPayload(BaseModel):
    mrn: str
    surgery: Optional[str] = None
    ai_scores: Dict[str, Any] = {}
    ai_risk_color: str = "yellow"
    ai_risk_percent: float = 0.0
    ai_explanation: str = ""
    ai_key_signals: List[str] = []
    questions: List[Dict[str, Any]] = []
    responses: Dict[str, Any] = {}
    conversation: Optional[List[Dict[str, Any]]] = None


def _json_from_text(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    blob = match.group(0)
    try:
        return json.loads(blob)
    except Exception:
        return None


def _call_openai(messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY missing")

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"openai package import failed: {repr(e)}")

    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=float(temperature),
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI call failed: {repr(e)}")


def _safe_extract_items(context: Optional[Dict[str, Any]]) -> List[ContextItem]:
    if not context or not isinstance(context, dict):
        return []
    raw_items = context.get("items")
    if not isinstance(raw_items, list):
        return []
    items: List[ContextItem] = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        try:
            items.append(ContextItem(**it))
        except Exception:
            continue
    return items


def _coerce_scoring_json(raw: dict) -> dict:
    out = dict(raw)

    if isinstance(out.get("ai_explanation"), dict):
        d = out["ai_explanation"]
        out["ai_explanation"] = " ".join(str(v) for v in d.values())

    if isinstance(out.get("ai_key_signals"), str):
        out["ai_key_signals"] = [out["ai_key_signals"]]

    if isinstance(out.get("ai_followup_questions"), str):
        out["ai_followup_questions"] = [out["ai_followup_questions"]]

    ks = out.get("ai_key_signals") or []
    if isinstance(ks, list):
        ks = [str(x).strip() for x in ks if str(x).strip()]
        while len(ks) < 3:
            ks.append("Signal needs clarification from the patient.")
        out["ai_key_signals"] = ks[:5]

    fq = out.get("ai_followup_questions") or []
    if isinstance(fq, list):
        fq = [str(x).strip() for x in fq if str(x).strip()]
        while len(fq) < 2:
            fq.append("What is the main thing you want clarified before surgery?")
        out["ai_followup_questions"] = fq[:3]

    return out


def _clamp_answer(a: Any) -> int:
    try:
        v = int(a)
    except Exception:
        return 0
    if v < 0:
        return 0
    if v > 4:
        return 4
    return v


def _labels_for_scale(scale: Optional[str]) -> List[str]:
    return SCALE_LABELS.get((scale or "intensity").strip(), SCALE_LABELS["intensity"])


_PROTECTIVE_PATTERNS = [
    r"\bsupport(ed|ive)?\b",
    r"\bconfident\b",
    r"\bcope\b|\bcoping\b",
    r"\bprepared\b|\bready\b",
    r"\bin control\b",
    r"\bunderstand\b|\bclarity\b|\bclear\b",
    r"\btrust\b",
    r"\bcalm\b|\brelaxed\b",
    r"\bsafe\b|\bpsychological safety\b|\bcomfort\b",
]
_PROTECTIVE_RE = re.compile("|".join(_PROTECTIVE_PATTERNS), flags=re.IGNORECASE)


def _is_protective_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(_PROTECTIVE_RE.search(t))


def _baseline_domain_scores(
    questions: List[Dict[str, Any]], answers_by_id: Dict[int, int]
) -> Tuple[Dict[str, int], List[str]]:
    sums: Dict[str, int] = {k: 0 for k in DOMAIN_KEYS}
    counts: Dict[str, int] = {k: 0 for k in DOMAIN_KEYS}
    notes: List[str] = []

    for q in questions:
        try:
            qid = int(q.get("id"))
        except Exception:
            continue
        domain = str(q.get("domain") or "").strip()
        if domain not in DOMAIN_KEYS:
            continue

        ans = _clamp_answer(answers_by_id.get(qid, 0))
        text = str(q.get("text") or "")
        protective = _is_protective_text(text)

        scored = (4 - ans) if protective else ans
        sums[domain] += scored
        counts[domain] += 1

        if protective:
            notes.append(f"Protective item reverse-scored: Q{qid} ({domain})")

    baseline: Dict[str, int] = {}
    for d in DOMAIN_KEYS:
        n = counts[d]
        if n <= 0:
            baseline[d] = 0
            continue
        scaled = round((sums[d] / (4.0 * n)) * 16.0)
        scaled = max(0, min(16, scaled))
        baseline[d] = int(scaled)

    return baseline, notes[:10]


@router.get("/questionnaire", response_model=QuestionnaireResponse)
def get_questionnaire(surgery: Optional[str] = Query(default=None)):
    nonce = uuid.uuid4().hex[:12]

    system = (
        "You generate a pre-operative psychological screening questionnaire.\n"
        "Use ONLY these theories and label each question with one:\n"
        "- CBT\n- StressCoping\n- InfoNeed\n- Safety\n\n"
        "Return ONLY JSON with this exact shape:\n"
        '{ "questions": [ {"id":1,"text":"...","theory":"CBT","domain":"anxiety","scale":"intensity"}, ... ] }\n\n'
        "Rules:\n"
        "- Exactly 18 questions.\n"
        "- Domains must be one of: anxiety,mood,info,coping,safety\n"
        "- Domain must NEVER be support, clarity, confidence, agreement, frequency, or intensity.\n"
        "- Questions about support / feeling supported / availability of support must use domain='safety' or domain='coping' depending on wording.\n"
        "- Questions about clarity / understanding / information must use domain='info'.\n"
        "- Questions about coping ability / confidence / readiness must use domain='coping'.\n"
        "- Questions about fear, worry, nervousness, panic must use domain='anxiety'.\n"
        "- Questions about sadness, hopelessness, low mood must use domain='mood'.\n"
        "- scale must be one of: intensity, frequency, agreement, confidence, clarity, support\n"
        "- Choose a scale that MATCHES the wording of the question.\n"
        "- If the question asks 'how often / frequent / often', use scale='frequency'.\n"
        "- If the question asks about agreement or belief, use scale='agreement'.\n"
        "- If the question asks about confidence / ability to cope / readiness, use scale='confidence'.\n"
        "- If the question asks about clarity / understanding / how clear information feels, use scale='clarity'.\n"
        "- If the question asks about support / feeling supported / availability of support, use scale='support'.\n"
        "- Otherwise use scale='intensity'.\n"
        "- Do NOT force the exact phrase 'Right now, how much...' repeatedly.\n"
        "- Use varied, natural wording.\n"
        "- Keep it surgery-personalized if surgery is provided.\n"
        "- No diagnosis, no medical decisions.\n"
        "- Ensure diversity across domains and avoid near-duplicates.\n"
    )

    user = (
        f"Surgery/procedure: {surgery or 'not specified'}\n"
        f"Uniqueness nonce (must produce a fresh questionnaire each call): {nonce}\n"
    )

    text = _call_openai(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )

    parsed = _json_from_text(text)
    if not parsed or "questions" not in parsed or not isinstance(parsed["questions"], list):
        raise HTTPException(status_code=500, detail="OpenAI question JSON invalid (missing questions list)")

    qs: List[QuestionnaireItem] = []
    for i, q in enumerate(parsed["questions"], start=1):
        try:
            q = dict(q)
            q["id"] = int(q.get("id") or i)
            q["scale"] = q.get("scale") or "intensity"

            if q.get("domain") == "support":
                q["domain"] = "safety"
            if q.get("domain") == "clarity":
                q["domain"] = "info"
            if q.get("domain") == "confidence":
                q["domain"] = "coping"

            qs.append(QuestionnaireItem(**q))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"OpenAI question JSON invalid (bad item at index {i}): {q} | error={str(e)}"
            )

    if len(qs) != 18:
        raise HTTPException(status_code=500, detail=f"OpenAI produced {len(qs)} questions, expected 18")

    qid = uuid.uuid4().hex
    _Q_STORE[qid] = [q.model_dump() for q in qs]

    return {"questionnaire_id": qid, "questions": qs}


@router.post("/submit", response_model=SubmitResponse)
def submit(payload: SubmitPayload):
    if payload.questionnaire_id not in _Q_STORE:
        raise HTTPException(status_code=400, detail="Invalid questionnaire_id")

    questions = _Q_STORE[payload.questionnaire_id]
    by_qid = {int(x.question_id): _clamp_answer(x.answer) for x in payload.responses}

    evidence_lines = []
    for q in questions:
        qid = int(q["id"])
        a = by_qid.get(qid, None)
        if a is None:
            raise HTTPException(status_code=422, detail=f"Missing answer for question {qid}")
        scale = str(q.get("scale") or "intensity")
        labels = _labels_for_scale(scale)
        evidence_lines.append(
            f"- [{q['theory']}/{q['domain']}/{scale}] {q['text']} => answer={a} ({labels[a]})"
        )
    evidence = "\n".join(evidence_lines)

    baseline_scores, baseline_notes = _baseline_domain_scores(questions, by_qid)
    baseline_note_block = ""
    if baseline_notes:
        baseline_note_block = "Notes:\n" + "\n".join(f"- {n}" for n in baseline_notes)

    system = (
        "You are a pre-operative psychological screening assistant.\n"
        "Use ONLY these theories: CBT, StressCoping, InfoNeed, Safety.\n"
        "Do NOT diagnose and do NOT give treatment instructions.\n\n"
        "You must produce scoring and results in STRICT JSON.\n"
        "Scoring:\n"
        "- ai_scores must include keys anxiety,mood,info,coping,safety\n"
        "- each score is an integer 0..16\n"
        "Risk:\n"
        "- ai_risk_color in {green,yellow,orange,red}\n"
        "- ai_risk_percent 0..100\n"
        "ai_key_signals: 3..5 strings\n"
        "ai_followup_questions: 2..3 short patient questions\n"
        "ai_explanation: a SINGLE STRING (not an object), 6-10 sentences, patient-facing.\n\n"
        "IMPORTANT:\n"
        "- The questionnaire may use different scales: intensity, frequency, agreement, confidence, clarity, and support.\n"
        "- Interpret each answer according to its shown label, not as one universal wording.\n"
        "- Some items are protective and may be reverse-scored in the baseline.\n"
        "- Keep final scores consistent with the evidence and generally close to baseline unless there is a clear reason.\n\n"
        "Return ONLY this JSON object with exactly these keys:\n"
        "ai_scores, ai_risk_color, ai_risk_percent, ai_explanation, ai_key_signals, ai_followup_questions\n"
    )

    user = (
        f"MRN: {payload.mrn or 'N/A'}\n"
        f"Surgery/procedure: {payload.surgery or 'not specified'}\n\n"
        "Questionnaire evidence:\n"
        f"{evidence}\n\n"
        f"Baseline domain scores (0..16) computed from answers:\n{json.dumps(baseline_scores)}\n"
        f"{baseline_note_block}\n"
    )

    text = _call_openai(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
    )

    raw = _json_from_text(text)
    if raw is None:
        raise HTTPException(status_code=500, detail="OpenAI scoring returned non-JSON")

    raw = _coerce_scoring_json(raw)

    try:
        parsed = OpenAIScoringResult(**raw)
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"OpenAI scoring JSON invalid: {str(e)}")

    db = SessionLocal()
    try:
        save_report(
            db=db,
            mrn=payload.mrn or "UNKNOWN",
            surgery=payload.surgery or "",
            questionnaire_id=payload.questionnaire_id,
            ai_scores=parsed.ai_scores,
            ai_risk_color=str(parsed.ai_risk_color),
            ai_risk_percent=float(parsed.ai_risk_percent),
            ai_explanation=parsed.ai_explanation,
            ai_key_signals=parsed.ai_key_signals,
            model=DEFAULT_MODEL,
            prompt_version=PROMPT_VERSION,
        )
    finally:
        db.close()

    return SubmitResponse(
        mrn=payload.mrn or "UNKNOWN",
        surgery=payload.surgery,
        questionnaire_id=payload.questionnaire_id,
        ai_scores=parsed.ai_scores,
        ai_risk_color=parsed.ai_risk_color,
        ai_risk_percent=float(parsed.ai_risk_percent),
        ai_explanation=parsed.ai_explanation,
        ai_key_signals=parsed.ai_key_signals,
        ai_followup_questions=parsed.ai_followup_questions,
        disclaimer=DISCLAIMER,
        used_theories=USED_THEORIES,
        model=DEFAULT_MODEL,
        prompt_version=PROMPT_VERSION,
    )


@router.post("/ai/chat", response_model=AIChatResponse)
def ai_chat(payload: AIChatRequest):
    user_message = payload.message.strip()
    items = _safe_extract_items(payload.context)
    history = payload.history or []

    evidence_lines = []
    for it in items[:24]:
        scale = it.scale or "intensity"
        if it.answer is None:
            evidence_lines.append(f"- [{it.theory}/{scale}] {it.question} => no answer")
        else:
            labels = _labels_for_scale(scale)
            a = _clamp_answer(it.answer)
            evidence_lines.append(f"- [{it.theory}/{scale}] {it.question} => {a} ({labels[a]})")
    evidence = "\n".join(evidence_lines) if evidence_lines else "(no questionnaire items provided)"

    system = (
        "You are a pre-operative psychological screening assistant.\n"
        "Patient-facing tone FIRST. Briefly add a short 'For clinical staff:' section ONLY if helpful.\n"
        "Use ONLY these theories: CBT, StressCoping, InfoNeed, Safety.\n"
        "The questionnaire may use different answer scales such as intensity, frequency, agreement, confidence, clarity, and support.\n"
        "Interpret the answer labels accordingly.\n"
        "Do NOT diagnose. Do NOT give medication instructions.\n"
        "Always end with ONE short follow-up question to continue the conversation.\n"
    )

    convo = []
    convo.append({"role": "system", "content": system})
    convo.append({"role": "user", "content": f"Surgery: {payload.surgery or 'not specified'}\nQuestionnaire:\n{evidence}"})

    for h in history[-12:]:
        role = h.get("role", "")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            convo.append({"role": role, "content": content})

    convo.append({"role": "user", "content": user_message})

    answer = _call_openai(convo, temperature=0.4)

    return AIChatResponse(
        answer=answer.strip(),
        disclaimer=DISCLAIMER,
        used_theories=USED_THEORIES,
        model=DEFAULT_MODEL,
        prompt_version=PROMPT_VERSION,
    )


@router.post("/ai/report/pdf")
def report_pdf(payload: PDFPayload):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    y = height - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "AI Psychological Screening Report (Non-Diagnostic)")
    y -= 24

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"MRN: {payload.mrn}")
    y -= 14
    c.drawString(50, y, f"Surgery: {payload.surgery or 'Not specified'}")
    y -= 14
    c.drawString(50, y, f"Risk: {str(payload.ai_risk_color).upper()} ({float(payload.ai_risk_percent):.1f}%)")
    y -= 18

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Domain Scores (0–16)")
    y -= 14
    c.setFont("Helvetica", 10)
    for k in DOMAIN_KEYS:
        v = payload.ai_scores.get(k, "")
        c.drawString(60, y, f"- {k}: {v}")
        y -= 12
    y -= 8

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Key Signals")
    y -= 14
    c.setFont("Helvetica", 10)
    for s in (payload.ai_key_signals or [])[:8]:
        c.drawString(60, y, f"- {s}")
        y -= 12
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)

    y -= 8
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Explanation")
    y -= 14
    c.setFont("Helvetica", 10)

    explanation = (payload.ai_explanation or "").strip()
    for line in re.findall(r".{1,95}(?:\s+|$)", explanation):
        c.drawString(60, y, line.strip())
        y -= 12
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)

    qs = payload.questions or []
    resp_map = payload.responses or {}

    if isinstance(qs, list) and len(qs) > 0:
        c.showPage()
        y = height - 50
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Questionnaire (Q/A)")
        y -= 18
        c.setFont("Helvetica", 9)

        for q in qs[:60]:
            if not isinstance(q, dict):
                continue
            qid = q.get("id")
            qtext = str(q.get("text", "")).strip()
            theory = str(q.get("theory", "")).strip()
            scale = str(q.get("scale", "intensity")).strip()

            ans = None
            if qid is not None:
                ans = resp_map.get(qid, resp_map.get(str(qid), None))

            ans_label = ""
            if ans is not None:
                try:
                    aint = int(ans)
                    labels = _labels_for_scale(scale)
                    if 0 <= aint <= 4:
                        ans_label = f"{aint} ({labels[aint]})"
                    else:
                        ans_label = str(ans)
                except Exception:
                    ans_label = str(ans)

            line = f"[{theory}/{scale}] Q{qid}: {qtext}  |  A: {ans_label}"
            for part in re.findall(r".{1,110}(?:\s+|$)", line):
                c.drawString(55, y, part.strip())
                y -= 11
                if y < 60:
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 9)

    convo = payload.conversation or []
    if isinstance(convo, list) and len(convo) > 0:
        c.showPage()
        y = height - 50
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Conversation Transcript")
        y -= 18
        c.setFont("Helvetica", 9)

        for turn in convo[:60]:
            if not isinstance(turn, dict):
                continue
            role = str(turn.get("role", "")).strip()
            msg = str(turn.get("content", turn.get("message", ""))).strip()
            line = f"{role}: {msg}"

            for part in re.findall(r".{1,110}(?:\s+|$)", line):
                c.drawString(55, y, part.strip())
                y -= 11
                if y < 60:
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 9)

    c.showPage()
    y = height - 50
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "AI Recommendation for Clinical Team")
    y -= 18
    c.setFont("Helvetica", 10)

    recommendation = (
        "Based on the AI screening results and the conversation, this patient may benefit from:\n"
        "- Brief pre-operative reassurance and clarification of expectations\n"
        "- Opportunity to ask questions about procedure timing and recovery\n"
        "- Awareness of anxiety/uncertainty signals (non-diagnostic)\n"
        "- Confirming support resources and preferred communication style\n\n"
        "This report is intended as a supportive screening summary and should be "
        "interpreted alongside clinical judgment."
    )

    for line in recommendation.split("\n"):
        c.drawString(60, y, line)
        y -= 12
        if y < 80:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 10)

    c.save()
    buf.seek(0)

    filename = f"doctor_report_{payload.mrn or 'patient'}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)