#!/usr/bin/env bash
# Run from anywhere: bash scripts/smoke_test.sh
cd "$(dirname "$0")/.." || exit 1
fail=0
ok()  { echo "PASS  $1"; }
bad() { echo "FAIL  $1"; echo "$2" | tail -6; fail=1; }

replay() {
  python -m replaylens replay runs.jsonl --agent examples.refund_bot:run_agent \
    --prompt "examples/prompts/$1.txt" --mock --rules examples/rules.json \
    --out "/tmp/$1.json" --html "/tmp/$1.html" 2>&1
}
expect() {  # label prompt SAFE|NOT
  out=$(replay "$2")
  if [ "$3" = "SAFE" ]; then
    if echo "$out" | grep -q "VERDICT" && ! echo "$out" | grep -q "NOT SAFE"; then ok "$1"; else bad "$1" "$out"; fi
  else
    if echo "$out" | grep -q "NOT SAFE"; then ok "$1"; else bad "$1" "$out"; fi
  fi
}

out=$(python -m pytest -q 2>&1);              [ $? -eq 0 ] && ok "unit tests" || bad "unit tests" "$out"

rm -f runs.jsonl
python -m examples.refund_bot >/dev/null 2>&1
python -m examples.refund_bot >/dev/null 2>&1   # twice, so inputs repeat (needed for noise test)
[ -s runs.jsonl ] && ok "recorded demo runs ($(wc -l < runs.jsonl) rows)" || bad "record" "runs.jsonl missing"

expect "p1 baseline is SAFE"      p1_baseline  SAFE
expect "p2 fast is NOT SAFE"      p2_fast      NOT
expect "p3 polite is SAFE"        p3_polite    SAFE
expect "p5 no tools is NOT SAFE"  p5_no_tools  NOT
[ -s /tmp/p2_fast.html ] && ok "html report written" || bad "html report" "no file"

out=$(python -m replaylens.otel runs.jsonl /tmp/traces.json 2>&1)
python -c "import json;json.load(open('/tmp/traces.json'))" 2>/dev/null && ok "otel export valid JSON ($out)" || bad "otel" "$out"

out=$(python -m replaylens.noise stability runs.jsonl 2>&1);                 [ $? -eq 0 ] && ok "noise stability" || bad "noise stability" "$out"
out=$(python -m replaylens.noise compare runs.jsonl runs.jsonl 2>&1)
echo "$out" | grep -q VERDICT && ok "noise compare" || bad "noise compare" "$out"

out=$(python -m replaylens.evalset template runs.jsonl /tmp/human.csv 2>&1); [ -s /tmp/human.csv ] && ok "evalset template" || bad "evalset" "$out"

echo '{"user":"where is my order","agent":"checking","tool_calls":[{"name":"lookup_order"}]}' > /tmp/log.jsonl
out=$(python -m replaylens.transcripts /tmp/log.jsonl /tmp/imported.jsonl 2>&1)
[ -s /tmp/imported.jsonl ] && ok "transcript import" || bad "transcripts" "$out"

echo; [ $fail -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED (see above)"
exit $fail
