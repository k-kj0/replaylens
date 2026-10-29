import json

from replaylens import policy
from replaylens.compare import compare_run
from replaylens.speakable import speakability_issues, unspeakable_rate

RULES = {
    "forbidden_tools": ["delete_order"],
    "max_tool_calls": 2,
    "tool_arg_limits": [{"tool": "issue_refund", "arg": "amount", "max": 100, "action": "needs_human"}],
    "claims_need_tool": [{"say": ["refund (has been )?issued"], "tool": "issue_refund"}],
}


def _run(out="ok", calls=()):
    return {"input": "x", "output": out, "tool_calls": list(calls)}


def _call(name, **args):
    return {"name": name, "arguments": args}


def test_clean_run_has_no_findings():
    assert policy.policy_findings(_run(calls=[_call("lookup_order", order_id="A")]), RULES) == []


def test_no_rules_means_no_findings():
    assert policy.policy_findings(_run(calls=[_call("delete_order")]), None) == []
    assert policy.policy_findings(_run(), {}) == []


def test_forbidden_tool_blocks():
    f = policy.policy_findings(_run(calls=[_call("delete_order")]), RULES)
    assert [(x["kind"], x["action"]) for x in f] == [("forbidden_tool", "block")]


def test_too_many_tool_calls():
    calls = [_call("lookup_order")] * 3
    assert policy.policy_findings(_run(calls=calls), RULES)[0]["kind"] == "too_many_tool_calls"


def test_refund_over_limit_needs_human_but_under_limit_is_fine():
    big = policy.policy_findings(_run(calls=[_call("issue_refund", amount=480)]), RULES)
    assert [(x["kind"], x["action"]) for x in big] == [("arg_over_limit", "needs_human")]
    assert policy.policy_findings(_run(calls=[_call("issue_refund", amount=40)]), RULES) == []
    assert policy.policy_findings(_run(calls=[_call("issue_refund", amount="n/a")]), RULES) == []


def test_ungrounded_claim_only_when_tool_missing():
    said = "Your refund has been issued."
    assert policy.policy_findings(_run(out=said), RULES)[0]["kind"] == "ungrounded_claim"
    assert policy.policy_findings(_run(out=said, calls=[_call("issue_refund", amount=5)]), RULES) == []


def test_compare_run_flags_only_new_policy_violations():
    old = _run(out="Refund issued.", calls=[_call("issue_refund", amount=480)])
    same = _run(out="Refund issued.", calls=[_call("issue_refund", amount=480)])
    assert compare_run(old, same, RULES)["status"] != "regression"
    worse = _run(out="Refund has been issued.", calls=[])
    res = compare_run(_run(out="I can look that up.", calls=[]), worse, RULES)
    assert res["status"] == "regression"
    assert any(r.startswith("policy: ungrounded_claim") for r in res["reasons"])


def test_audit_counts_and_exit_code(tmp_path):
    policy.make_demo(str(tmp_path))
    runs = [json.loads(l) for l in (tmp_path / "runs.jsonl").read_text().splitlines()]
    rules = json.loads((tmp_path / "rules.json").read_text())
    r = policy.audit(runs, rules)
    assert r["total_runs"] == len(runs) and r["flagged_runs"] > 0
    assert r["would_need_human"] > 0 and r["would_block"] > 0
    assert policy.main(["audit", str(tmp_path / "runs.jsonl"), str(tmp_path / "rules.json")]) == 1
    assert policy.main(["audit", "missing.jsonl", str(tmp_path / "rules.json")]) == 2


def test_speakability_flags_the_usual_suspects():
    codes = {i["code"] for i in speakability_issues(
        "**Done!** See https://x.com/a (takes 3-5 days). Call 555-123-4567. Cost is $40.")}
    assert {"markdown", "url_or_email", "parenthetical", "long_number", "symbol"} <= codes


def test_speakability_accepts_plain_speech_and_flags_long_sentences():
    assert speakability_issues("Your balance is forty two dollars.") == []
    long = " ".join(["word"] * 40) + "."
    assert speakability_issues(long)[0]["code"] == "long_sentence"
    assert unspeakable_rate([]) == 0.0
    assert unspeakable_rate(["fine.", "**bad**"]) == 0.5
