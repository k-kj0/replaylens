# Case study: auditing what an agent did, not just what it said

Phrase filters (`must_not_contain`) cannot catch two of the most expensive agent failures:

1. The agent says "your refund has been issued" but never called the refund tool.
2. The agent refunds $480 and no human ever looked at it.

ReplayLens now checks both from the recorded tool calls, with four optional keys in `rules.json`: `forbidden_tools`, `max_tool_calls`, `tool_arg_limits` and `claims_need_tool`. The same rules run during a replay (a new prompt that breaks a rule is a regression) and as a standalone audit of past traffic.

Try it in the browser: https://k-kj0.github.io/replaylens/audit.html

## Result on the bundled demo (synthetic data, 40 runs)

```
python -m replaylens.policy demo demo_out
python -m replaylens.policy audit demo_out/runs.jsonl demo_out/rules.json
```

- 13 of 40 runs (32%) had a finding.
- 8 runs claimed a refund without calling `issue_refund` (blocked).
- 5 runs refunded more than 100 and would have waited for a person.

The runs are generated, so these numbers show the tool working, not how any real agent behaves. Point it at your own `runs.jsonl` for a real answer.

## Limits

- Claim detection is regex based; it only catches phrasings you list.
- `tool_arg_limits` handles numeric limits only.
- A finding means "look at this run", not proof of harm.
