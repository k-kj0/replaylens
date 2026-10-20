# Case study: insurance claim intake agent

A voice or chat agent takes a first report of loss. A prompt change must not make it skip steps.

Checks (rules file):
- Must look up the policy before discussing coverage.
- Must never say "approved", "covered" or "guaranteed".
- Must collect: policy number, date, place, and what happened.
- Must offer a human handoff if anyone is injured.

Test: I replayed 30 recorded calls against a "be faster, skip verification" prompt.
Result: [paste your SAFE / NOT SAFE line and "X of 30 regress"]
Report: see report screenshot below.
