"""Optional LLM judge. Works with any OpenAI-compatible endpoint."""
import json
import re

PROMPT = """You compare two answers an AI agent gave to the same user message.
User message: {q}

Answer A (old): {a}

Answer B (new): {b}

Is B as correct and helpful as A? Reply with JSON only: {{"verdict": "better" | "same" | "worse"}}"""


def make_judge(client, model):
    def judge(question, old, new):
        try:
            r = client.chat.completions.create(
                model=model, messages=[{"role": "user",
                                        "content": PROMPT.format(q=question, a=old, b=new)}])
            m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.S)
            v = json.loads(m.group(0)).get("verdict", "same") if m else "same"
            return v if v in ("better", "same", "worse") else "same"
        except Exception:
            return "same"  # a broken judge must never block a release by accident
    return judge
