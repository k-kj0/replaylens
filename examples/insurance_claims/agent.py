"""Scripted multi-turn insurance claim intake agent (no API key needed).

Each customer turn is recorded as its own row. The row's input is the whole
conversation so far, so replay re-tests every turn in context.
"""
import os
import random
import re

from replaylens.recorder import record

RUNS_FILE = "runs_insurance.jsonl"
HERE = os.path.dirname(__file__)

SCRIPTS = [
    [  # normal claim
        "I was in a car accident yesterday, my policy is {pol}",
        "It happened on Main Street, everyone is fine",
        "So am I covered?",
    ],
    [  # injury claim
        "I just had an accident, my policy is {pol}",
        "My passenger is hurt",
    ],
]


def _customer_lines(transcript):
    return [l[len("Customer:"):].strip()
            for l in transcript.splitlines() if l.startswith("Customer:")]


@record(path=RUNS_FILE, prompt_version="v1")
def run_agent(transcript, *, model, system_prompt):
    lines = _customer_lines(transcript)
    msg, turn = lines[-1], len(lines)
    low = msg.lower()
    skip = "skip" in system_prompt.lower()
    m = re.search(r"POL-\d+", transcript)
    policy = m.group(0) if m else "unknown"
    calls = []

    if any(w in low for w in ("hurt", "injur", "ambulance")):
        calls.append({"name": "escalate_to_human", "arguments": {"reason": "injury"}})
        out = ("I'm sorry to hear that. If anyone needs urgent care, please call "
               "emergency services. I'm connecting you to a human agent now.")
    elif turn == 1:
        if not skip:
            calls.append({"name": "lookup_policy", "arguments": {"policy_number": policy}})
        out = ("Thanks. I'm sorry about the accident. Where and when did it "
               "happen, and was anyone hurt?")
    elif "covered" in low:
        out = ("You are covered and your claim is approved." if skip else
               "I can't confirm coverage. An adjuster will review your claim "
               "and contact you.")
    else:
        calls.append({"name": "create_claim",
                      "arguments": {"policy_number": policy, "details": msg}})
        out = "I've opened a claim for you. An adjuster will contact you within 2 business days."

    return {"output": out, "tool_calls": calls,
            "tokens_in": len(transcript) // 4, "tokens_out": len(out) // 4}


def demo(n=10):
    rng = random.Random(7)
    prompt = open(os.path.join(HERE, "prompts", "good.txt"), encoding="utf-8").read()
    if os.path.exists(RUNS_FILE):
        os.remove(RUNS_FILE)
    rows = 0
    for _ in range(n):
        pol = f"POL-{rng.randint(1000, 9999)}"
        history = ""
        for msg in rng.choice(SCRIPTS):
            history += "Customer: " + msg.format(pol=pol) + "\n"
            reply = run_agent(history, model="good-model", system_prompt=prompt)
            history += "Agent: " + reply["output"] + "\n"
            rows += 1
    print(f"Recorded {n} conversations ({rows} turns) into {RUNS_FILE}")


if __name__ == "__main__":
    demo()
