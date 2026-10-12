import os, sys, random
os.environ["REPLAYLENS_MOCK"] = ""
from examples.refund_bot import run_agent, QUESTIONS
prompt = open("examples/prompts/v1.txt").read()
rng = random.Random(7)
if os.path.exists("runs.jsonl"): os.remove("runs.jsonl")
for _ in range(10):
    q = rng.choice(QUESTIONS).format(n=1000 + rng.randint(1, 10))
    run_agent(q, model=sys.argv[1], system_prompt=prompt)
print("recorded 10 real runs")
