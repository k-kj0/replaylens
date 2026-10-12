import sys, json
ids = sorted(m['id'] for m in json.load(sys.stdin)['data'])
bad = ('guard', 'safeguard', 'whisper', 'orpheus', 'tts', 'embed', 'prompt-guard')
ok = [i for i in ids if not any(b in i.lower() for b in bad)]
sys.stderr.write("All models:\n  " + "\n  ".join(ids) + "\n")
for key in ('llama-3.3-70b', 'gpt-oss-120b', 'gpt-oss-20b', 'llama', 'qwen', 'kimi'):
    for i in ok:
        if key in i.lower():
            print(i); sys.exit(0)
print(ok[0] if ok else "NONE")
