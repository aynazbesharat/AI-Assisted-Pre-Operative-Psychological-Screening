import random

DOMAINS = ["anxiety", "mood", "info", "coping", "safety"]

CONTEXT_OPTIONS = [
    "the upcoming surgery",
    "the medical procedure",
    "what the doctors will do",
    "the recovery period",
    "possible complications",
    "how long the procedure will take",
    "being in the hospital environment",
    "the medical equipment used during surgery",
    "the anesthesia process",
    "not knowing who will be present",
    "the level of pain you might experience",
    "unexpected changes during surgery",
    "the hospital staff involved",
    "the preparation steps before surgery",
    "how well the surgery will go",
    "your safety during the procedure",
    "the risk of unexpected outcomes",
    "what you will feel during recovery",
    "the level of support you will receive",
    "the uncertainty surrounding the procedure",
]

TEMPLATES = {
    "anxiety": [
        "How often do you feel anxious when thinking about {context}?",
        "Does uncertainty about {context} increase your anxiety levels?",
        "Do intrusive thoughts about {context} make you feel uneasy?",
        "Does anticipating {context} cause you to feel tense or nervous?",
        "Do you feel distressed when you imagine possible outcomes related to {context}?",
    ],
    "mood": [
        "Does thinking about {context} negatively affect your mood?",
        "How often do you feel less motivated when thinking about {context}?",
        "Does worry about {context} make it harder for you to stay positive?",
        "Do you feel emotionally low when considering {context}?",
    ],
    "info": [
        "Do you feel you need more information or clarity about {context}?",
        "Does uncertainty about {context} make you want more details?",
        "Would more explanation about {context} help you feel calmer?",
        "Do you feel you are not fully informed about {context}?",
    ],
    "coping": [
        "How confident are you in your ability to cope with stress related to {context}?",
        "Do you struggle to calm yourself when thinking about {context}?",
        "Do you feel you have enough coping strategies for stress related to {context}?",
        "When you think about {context}, can you manage your emotions effectively?",
    ],
    "safety": [
        "Does thinking about {context} affect your sense of safety?",
        "Do concerns about personal safety increase when considering {context}?",
        "Do you feel unsafe when imagining scenarios connected to {context}?",
        "Does uncertainty about {context} make you feel more vulnerable?",
    ],
}

EXPLANATIONS = {
    "anxiety": "This question reflects emotional response.",
    "mood": "This question reflects mood and motivation.",
    "info": "This question reflects information need and reassurance.",
    "coping": "This question reflects coping and emotion regulation.",
    "safety": "This question reflects emotional or procedural safety.",
}

TYPE_BY_DOMAIN = {
    "anxiety": "emotion",
    "mood": "frequency",
    "info": "info_need",
    "coping": "coping",
    "safety": "safety",
}

def generate_local_questions(seed: int = 42):
    rng = random.Random(seed)

    counts = {"anxiety": 4, "mood": 4, "info": 4, "coping": 3, "safety": 3}

    used_contexts = set()
    used_texts = set()

    questions = []
    qid = 1

    for domain in ["anxiety", "mood", "info", "coping", "safety"]:
        for _ in range(counts[domain]):
            text = None
            for _try in range(50):
                template = rng.choice(TEMPLATES[domain])

                available = [c for c in CONTEXT_OPTIONS if c not in used_contexts]
                context = rng.choice(available) if available else rng.choice(CONTEXT_OPTIONS)

                candidate = template.format(context=context).strip()

                if candidate not in used_texts:
                    text = candidate
                    used_texts.add(text)
                    used_contexts.add(context)
                    break

            if text is None:
                template = rng.choice(TEMPLATES[domain])
                context = rng.choice(CONTEXT_OPTIONS)
                text = template.format(context=context).strip()
                used_texts.add(text)
                used_contexts.add(context)

            questions.append(
                {
                    "id": qid,
                    "domain": domain,
                    "text": text,
                    "type": TYPE_BY_DOMAIN[domain],
                    "explanation": EXPLANATIONS[domain],
                }
            )
            qid += 1

    return questions
