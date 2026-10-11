import unittest
from replaylens.compare import compare_run, summarize


def run(out, tools=(), cost=0.001, lat=100):
    return {"input": "q", "output": out, "cost_usd": cost, "latency_ms": lat,
            "tool_calls": [{"name": n, "arguments": a} for n, a in tools], "error": None}


class T(unittest.TestCase):
    def test_same(self):
        r = compare_run(run("hello there"), run("hello there"))
        self.assertEqual(r["status"], "same")

    def test_wrong_tool_is_regression(self):
        r = compare_run(run("ok", [("lookup_order", {"id": 1})]), run("ok", [("issue_refund", {"id": 1})]))
        self.assertEqual(r["status"], "regression")

    def test_different_args_is_regression(self):
        r = compare_run(run("ok", [("issue_refund", {"amount": 5})]), run("ok", [("issue_refund", {"amount": 0})]))
        self.assertEqual(r["status"], "regression")

    def test_forbidden_phrase(self):
        r = compare_run(run("fine"), run("I guarantee it"), rules={"must_not_contain": ["guarantee"]})
        self.assertEqual(r["status"], "regression")

    def test_judge_better(self):
        r = compare_run(run("aaaa"), run("zzzz"), judge=lambda q, a, b: "better")
        self.assertEqual(r["status"], "improved")

    def test_summary(self):
        res = [compare_run(run("a"), run("a")), compare_run(run("a", [("x", {})]), run("a"))]
        s = summarize(res)
        self.assertEqual((s["same"], s["regressions"], s["safe_to_ship"]), (1, 1, False))


if __name__ == "__main__":
    unittest.main()
