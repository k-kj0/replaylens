"""Demo agent: a refund bot with 2 tools. Run `python -m examples.refund_bot` to record 30 runs."""
import os
import random

from replaylens import record, run_tool_agent

ORDERS = {f"ORD-{1000 + i}": {"status": random.Random(i).choice(["delivered", "shipped", "processing"]),
                              "amount": 10 + i * 7} for i in range(1, 11)}

TOOLS = [
    {"type": "function", "function": {
        "name": "lookup_order", "description": "Get status and amount of an order",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}},
                       "required": ["order_id"]}}},
    {"type": "function", "function": {
        "name": "issue_refund", "description": "Refund an order",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"},
                                                        "amount": {"type": "number"}},
                       "required": ["order_id", "amount"]}}},
]


def lookup_order(order_id):
    return ORDERS.get(order_id, {"status": "not found", "amount": 0})


def issue_refund(order_id, amount):
    return {"ok": True, "order_id": order_id, "refunded": amount}


def get_client():
    if os.environ.get("REPLAYLENS_MOCK"):
        from examples.fake_llm import FakeClient
        return FakeClient()
    from openai import OpenAI  # reads OPENAI_API_KEY and OPENAI_BASE_URL from the environment
    return OpenAI()


@record(path="runs.jsonl", prompt_version="v1.txt", price_in=0.15, price_out=0.60)
def run_agent(user_input, *, model, system_prompt):
    return run_tool_agent(get_client(), model, system_prompt, user_input, TOOLS,
                          {"lookup_order": lookup_order, "issue_refund": issue_refund})


QUESTIONS = [
    "I want a refund for ORD-{n}", "Please refund ORD-{n}, it arrived broken",
    "Where is my order ORD-{n}?", "What is the status of ORD-{n}?",
    "I'd like my money back for ORD-{n}", "Can you help me?",
]


def demo(n=30):
    rng = random.Random(7)
    prompt = open(os.path.join(os.path.dirname(__file__), "prompts", "v1.txt")).read()
    if os.path.exists("runs.jsonl"):
        os.remove("runs.jsonl")
    for _ in range(n):
        q = rng.choice(QUESTIONS).format(n=1000 + rng.randint(1, 10))
        run_agent(q, model="good-model", system_prompt=prompt)
    print(f"Recorded {n} runs into runs.jsonl")


if __name__ == "__main__":
    os.environ.setdefault("REPLAYLENS_MOCK", "1")  # no API key needed for the demo
    demo()
