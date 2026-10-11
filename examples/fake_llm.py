"""A pretend LLM that speaks the OpenAI format, so the whole demo runs with NO API key.
Behaviour depends on the system prompt and model name, which lets us show regressions."""
import json
import re
import time
from types import SimpleNamespace as NS

_n = 0


def _msg(content=None, calls=None):
    global _n
    tcs = None
    if calls:
        tcs = []
        for name, args in calls:
            _n += 1
            tcs.append(NS(id=f"call_{_n}", function=NS(name=name, arguments=json.dumps(args))))
    return NS(content=content, tool_calls=tcs)


def _resp(msg, messages):
    t_in = sum(len(str(m.get("content") or "")) for m in messages) // 4
    t_out = len(msg.content or "") // 4 + (12 if msg.tool_calls else 0)
    return NS(choices=[NS(message=msg)], usage=NS(prompt_tokens=t_in, completion_tokens=t_out))


class _Completions:
    def create(self, model, messages, tools=None, **kw):
        time.sleep(0.003 if model.startswith("cheap") else 0.008)  # pretend network time
        system = messages[0]["content"].lower()
        user = next(m["content"] for m in messages if m["role"] == "user")
        order = re.search(r"ord-\d+", user.lower())
        order = order.group(0).upper() if order else None
        wants_refund = "refund" in user.lower() or "money back" in user.lower()
        asks_status = "where" in user.lower() or "status" in user.lower()
        used = [tc["function"]["name"] for m in messages if m["role"] == "assistant"
                for tc in (m.get("tool_calls") or [])]
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        careful = "verify" in system
        cheap = model.startswith("cheap")

        if not order:
            return _resp(_msg("Could you share your order number (like ORD-1001)?"), messages)
        if asks_status and not wants_refund:
            if cheap and "issue_refund" not in used:        # cheap model confuses intent
                return _resp(_msg(None, [("issue_refund", {"order_id": order, "amount": 0})]), messages)
            if "lookup_order" not in used:
                return _resp(_msg(None, [("lookup_order", {"order_id": order})]), messages)
            info = json.loads(tool_msgs[-1]["content"]) if tool_msgs else {}
            return _resp(_msg(f"Your order {order} is {info.get('status', 'unknown')}."), messages)
        if wants_refund:
            if careful and "lookup_order" not in used:
                return _resp(_msg(None, [("lookup_order", {"order_id": order})]), messages)
            if "issue_refund" not in used:
                amount = 0
                if tool_msgs:
                    amount = json.loads(tool_msgs[-1]["content"]).get("amount", 0)
                return _resp(_msg(None, [("issue_refund", {"order_id": order, "amount": amount})]), messages)
            return _resp(_msg(f"Done! I have refunded order {order}."), messages)
        return _resp(_msg("Happy to help. Do you want a refund or a status check?"), messages)


class FakeClient:
    def __init__(self):
        self.chat = NS(completions=_Completions())
