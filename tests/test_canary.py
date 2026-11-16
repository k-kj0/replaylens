import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from canary.client import call_provider
from canary.drift import evaluate, replay_alarm_rate
from canary.grade import GraderShapeError, grade
from canary.runner import run_once
from canary.stats import holm, mcnemar_exact, min_discordant, paired_bootstrap, wilson


# ---------- statistics ----------

def test_reproduces_openbenchmarks_published_example():
    # Statistical reporting post: A and B disagree on 16 tasks, A wins 14 (p = 0.004).
    assert round(mcnemar_exact(2, 14), 3) == 0.004


def test_mcnemar_no_disagreement_is_not_significant():
    assert mcnemar_exact(0, 0) == 1.0


def test_minimum_changed_tasks_for_significance_is_six():
    assert min_discordant(0.05) == 6
    assert mcnemar_exact(0, 5) > 0.05 > mcnemar_exact(0, 6)


def test_wilson_interval_for_small_public_set():
    low, high = wilson(26, 29)   # about 90 percent of 29 tasks
    assert 0.73 < low < 0.75 and 0.96 < high < 0.97


def test_holm_is_monotone_and_capped():
    adj = holm([0.01, 0.04, 0.03])
    assert adj[0] == pytest.approx(0.03) and max(adj) <= 1.0
    assert adj[2] >= adj[0] and adj[1] >= adj[2]


def test_paired_bootstrap_detects_a_clear_shift():
    point, low, high, p = paired_bootstrap([100.0 + i for i in range(20)])
    assert low > 0 and p < 0.01


# ---------- grading (rows follow the dataset card; check with `inspect`) ----------

MEETING = {"use_case": "meeting-notes-lookup", "gold": "Tuesday 3 PM", "aliases": ["tue 3pm"]}
TICKET = {"use_case": "ticket-triage", "gold": {"category": "billing", "priority": "high"}}
CONTRACT = {"use_case": "contract-terms-extraction",
            "gold": {"start": "2026-01-02", "auto_renew": True, "seats": None, "cap": 5}}


def test_meeting_accepts_alias_with_messy_spacing_and_case():
    assert grade(MEETING, '{"answer": "  TUE   3pm "}') == (True, "ok")
    assert grade(MEETING, '{"answer": "Friday"}') == (False, "wrong")
    assert grade(MEETING, '{"answer": "Tuesday 3 PM", "extra": 1}') == (False, "schema")


def test_ticket_requires_exact_lowercase_pair():
    assert grade(TICKET, '{"category": "billing", "priority": "high"}')[0]
    assert not grade(TICKET, '{"category": "Billing", "priority": "high"}')[0]
    assert grade(TICKET, '{"category": "billing"}') == (False, "schema")


def test_contract_is_typed_so_true_is_not_one():
    assert grade(CONTRACT, '{"start":"2026-01-02","auto_renew":true,"seats":null,"cap":5}')[0]
    assert not grade(CONTRACT, '{"start":"2026-01-02","auto_renew":1,"seats":null,"cap":5}')[0]
    assert not grade(CONTRACT, '{"start":"2026-01-02","auto_renew":true,"seats":null,"cap":5.0}')[0]


def test_bad_json_and_odd_rows():
    assert grade(MEETING, "not json") == (False, "malformed_json")
    assert grade(MEETING, "[1]") == (False, "not_object")
    with pytest.raises(GraderShapeError):
        grade({"use_case": "unknown-task", "gold": "x"}, "{}")


# ---------- client against a local fake streaming server ----------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _chunk(self, data):
        self.wfile.write(("%x\r\n" % len(data)).encode() + data + b"\r\n")
        self.wfile.flush()

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        mode = self.server.mode
        if mode == "429":
            self.send_response(429)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        if mode == "hang":
            time.sleep(1.5)
        pieces = [{"reasoning_content": "hmm"}, {"content": '{"answer":'}, {"content": ' "ok"}'}]
        for d in pieces:
            self._chunk(("data: " + json.dumps({"choices": [{"delta": d}]}) + "\n\n").encode())
            time.sleep(0.02)
        self._chunk(b"data: [DONE]\n\n")
        self.wfile.write(b"0\r\n\r\n")


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.mode = "ok"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()


def provider(srv):
    return {"name": "fake", "base_url": "http://127.0.0.1:%d/v1" % srv.server_port,
            "model": "m", "key_env": "NOPE"}


def test_client_streams_and_measures_first_token_times(server):
    r = call_provider(provider(server), [{"role": "user", "content": "hi"}], timeout_s=5)
    assert r["fail"] is None and r["text"] == '{"answer": "ok"}'
    assert 0 < r["ttft_ms"] <= r["ttv_ms"] <= r["e2e_ms"]


def test_client_classifies_429(server):
    server.mode = "429"
    assert call_provider(provider(server), [], timeout_s=5)["fail"] == "http_429"


def test_client_enforces_end_to_end_timeout_without_retry(server):
    server.mode = "hang"
    t0 = time.time()
    assert call_provider(provider(server), [], timeout_s=0.5)["fail"] == "timeout"
    assert time.time() - t0 < 1.4


def test_client_transport_error_when_nothing_listens():
    p = {"name": "x", "base_url": "http://127.0.0.1:9/v1", "model": "m"}
    assert call_provider(p, [], timeout_s=2)["fail"] == "transport"


# ---------- runner ----------

def test_runner_rotates_launch_order_and_grades():
    tasks = [dict(MEETING, id="t%d" % i, prompt={"system": "s", "user": "u"}) for i in range(4)]
    provs = [{"name": "a", "model": "m"}, {"name": "b", "model": "m"}]
    order = []

    def fake(p, messages, timeout_s):
        order.append(p["name"])
        return {"fail": None, "text": '{"answer": "tuesday 3 pm"}', "e2e_ms": 10.0, "ttft_ms": 5.0, "ttv_ms": 6.0}

    rows = run_once(tasks, provs, "abc123", call=fake)
    assert order == ["a", "b", "b", "a", "a", "b", "b", "a"]
    assert all(t["ok"] for r in rows for t in r["tasks"]) and len(rows) == 2


# ---------- drift ----------

def make_run(k, ok_flags, e2e=100.0, dataset="d1", provider_name="p"):
    return {"run_id": "r%03d" % k, "ts": "2026-11-%02dT00:00:00Z" % (k + 1), "provider": provider_name,
            "model": "m", "dataset_id": dataset,
            "tasks": [{"id": "t%d" % i, "ok": f, "fail": None, "why": "ok",
                       "e2e_ms": e2e + (i % 5), "ttft_ms": 1.0, "ttv_ms": 2.0}
                      for i, f in enumerate(ok_flags)]}


def test_quiet_history_raises_no_alarm_and_a_a_rate_is_zero():
    flags = [True] * 26 + [False] * 3
    rows = [make_run(k, flags) for k in range(20)]
    assert not any(f["flagged"] for f in evaluate(rows))
    alarms, checks, low, high = replay_alarm_rate(rows)
    assert alarms == 0 and checks == 13 and high < 0.3


def test_still_warming_up_gives_no_findings():
    rows = [make_run(k, [True] * 29) for k in range(5)]
    assert evaluate(rows) == []


def test_accuracy_drop_is_flagged():
    good, bad = [True] * 29, [False] * 9 + [True] * 20
    rows = [make_run(k, good) for k in range(8)] + [make_run(8, bad)]
    flagged = [f for f in evaluate(rows) if f["flagged"]]
    assert any(f["signal"] == "accuracy" and f["direction"] == "worse" for f in flagged)


def test_small_accuracy_change_cannot_be_significant():
    good, bad = [True] * 29, [False] * 4 + [True] * 25
    rows = [make_run(k, good) for k in range(8)] + [make_run(8, bad)]
    assert not any(f["flagged"] for f in evaluate(rows))


def test_latency_doubling_is_flagged_but_ten_percent_is_not():
    flags = [True] * 29
    slow = [make_run(k, flags) for k in range(8)] + [make_run(8, flags, e2e=220.0)]
    assert any(f["signal"] == "latency" and f["flagged"] for f in evaluate(slow))
    mild = [make_run(k, flags) for k in range(8)] + [make_run(8, flags, e2e=110.0)]
    assert not any(f["flagged"] for f in evaluate(mild))


def test_new_dataset_version_resets_the_baseline():
    flags = [True] * 29
    rows = [make_run(k, flags, dataset="old") for k in range(8)]
    rows.append(make_run(8, [False] * 29, dataset="new"))
    assert evaluate(rows) == []
