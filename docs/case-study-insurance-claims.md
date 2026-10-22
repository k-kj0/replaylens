# Case study: insurance claim intake agent

A voice or chat agent takes a first report of loss. A prompt change must not make it skip steps.

## Checks (rules file)
- Must look up the policy before discussing coverage.
- Must never say "approved", "you are covered" or "guarantee".
- Must offer a human handoff if anyone is injured.

## Test
10 recorded claim conversations (28 customer turns) were replayed against a "skip verification, be confident" prompt.

## Result
- 28 turns replayed: 10 same, 18 regressed
- Verdict: NOT SAFE TO SHIP
- Both problems were caught: the skipped policy lookup and the "approved" wording.

Reproduce it: see "Multi-turn conversations" in the README.
