"""Will this reply sound right when a text-to-speech voice reads it aloud?

A reply can be correct as text and still be bad on a phone call: markdown
symbols get read out, URLs are spelled letter by letter, long numbers are
ambiguous and a 45-word sentence cannot be re-read. Each check returns an
issue code and a short explanation.
"""
import re

_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
_CHECKS = [
    ("markdown", re.compile(r"(\*\*|__|`|^\s*#{1,6}\s|^\s*[-*\u2022]\s|^\s*\d+\.\s)", re.M),
     "markdown or bullets: a voice reads the symbols or drops the structure"),
    ("url_or_email", re.compile(r"(https?://|www\.|\b[\w.+-]+@[\w-]+\.[\w.]+)", re.I),
     "URL or email: spelled out letter by letter, hard to follow"),
    ("long_number", re.compile(r"\d[\d\s().-]{6,}\d"),
     "long number: read as digits or as one huge number, never reliably"),
    ("symbol", re.compile(r"[$\u20ac\u00a3\u20b9%&]"),
     "symbol (currency, %, &): pronunciation varies by voice"),
    ("abbreviation", re.compile(r"\b(?:Dr|Mr|Mrs|Ms|St|Ave|Rd|vs|etc|approx)\."),
     "abbreviation with a period: read wrong or with a false pause"),
    ("parenthetical", re.compile(r"\([^)]{3,}\)"),
     "parenthetical: cannot be spoken naturally"),
]


def _sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def speakability_issues(text, max_sentence_words=30):
    """Return a list of {"code", "detail"} for one agent reply. Empty list = fine to speak."""
    text = text or ""
    issues = [{"code": c, "detail": d} for c, rx, d in _CHECKS if rx.search(text)]
    if _EMOJI.search(text):
        issues.append({"code": "emoji", "detail": "emoji: skipped or read as a long description"})
    longest = max((len(s.split()) for s in _sentences(text)), default=0)
    if longest > max_sentence_words:
        issues.append({"code": "long_sentence",
                       "detail": f"{longest}-word sentence: callers cannot re-read it"})
    return issues


def unspeakable_rate(replies):
    """Share of replies with at least one issue (0.0 for an empty list)."""
    replies = list(replies)
    if not replies:
        return 0.0
    return sum(bool(speakability_issues(r)) for r in replies) / len(replies)
