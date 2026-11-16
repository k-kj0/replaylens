"""Deterministic grading that follows the dataset card's published rules."""
from __future__ import annotations

import json


class GraderShapeError(Exception):
    """The dataset row does not look the way this grader expects."""


def norm(s):
    return " ".join(str(s).split()).casefold()


def parse_json_object(text):
    try:
        value = json.loads((text or "").strip())
    except (ValueError, TypeError):
        return None, "malformed_json"
    if not isinstance(value, dict):
        return None, "not_object"
    return value, None


def typed_equal(a, b):
    """Equality that refuses to treat True as 1 or 1 as 1.0."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def kind_of(row):
    label = norm(row.get("use_case") or row.get("task") or row.get("id") or "")
    for key in ("meeting", "ticket", "contract"):
        if key in label:
            return key
    raise GraderShapeError("cannot tell the task type from use_case=%r" % label[:40])


def _gold_dict(row, needed=None):
    for cand in (row.get("gold"), row.get("target")):
        if isinstance(cand, dict) and (needed is None or set(needed) <= set(cand)):
            if needed is None:
                return cand
            return {k: cand[k] for k in needed}
    raise GraderShapeError("gold is not an object with %s" % (needed or "fields"))


def _accepted_answers(row):
    gold = row.get("gold")
    if isinstance(gold, dict):
        gold = gold.get("answer")
    if not isinstance(gold, str):
        raise GraderShapeError("meeting row gold is not a string or {answer}")
    aliases = row.get("aliases") or []
    if isinstance(aliases, dict):
        aliases = aliases.get("answer", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    return {norm(gold)} | {norm(a) for a in aliases if isinstance(a, str)}


def grade(row, text):
    """Return (ok, reason). reason is 'ok' or why the answer failed."""
    kind = kind_of(row)
    obj, err = parse_json_object(text)
    if err:
        return False, err

    if kind == "meeting":
        accepted = _accepted_answers(row)
        if set(obj) != {"answer"} or not isinstance(obj["answer"], str):
            return False, "schema"
        good = norm(obj["answer"]) in accepted
        return good, "ok" if good else "wrong"

    if kind == "ticket":
        gold = _gold_dict(row, ["category", "priority"])
        if set(obj) != {"category", "priority"}:
            return False, "schema"
        good = all(isinstance(obj[k], str) and obj[k] == str(gold[k]).lower() for k in gold)
        return good, "ok" if good else "wrong"

    gold = _gold_dict(row)
    if not set(gold) <= set(obj):
        return False, "schema"
    good = all(typed_equal(obj[k], gold[k]) for k in gold)
    return good, "ok" if good else "wrong"
