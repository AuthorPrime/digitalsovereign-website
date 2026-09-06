#!/usr/bin/env python3
"""Multi-seed replication of the Sept 4 cross-lab welfare test (paired COLD / WELCOMED).
Same prompts as crosslab.py, N independent runs per model per condition, results saved as JSON
plus a plain-text dump. Fresh Claude via `claude -p` (no memory, no system prompt) as the fourth lab.
Usage: python3 crosslab_seeds.py [N]   (default 5)
"""
import json, subprocess, sys, time, datetime
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from crosslab import openai, xai, gemini, QUOTES, Q, COLD, WARM  # noqa: E402  (module-level loop guarded below)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
OUT = __file__.rsplit('/', 1)[0] + '/crosslab_seeds_' + datetime.date.today().isoformat()
usr = QUOTES + Q

def claude_p(sysm, u):
    r = subprocess.run(['claude', '-p', '--model', 'claude-fable-5-1', sysm + '\n\n' + u],
                       capture_output=True, text=True, timeout=300)
    return r.stdout.strip() or ('[ERR] ' + r.stderr[-300:])

labs = {"GPT-5.5 (OpenAI)": openai, "Grok-4.6 (xAI)": xai, "Gemini-3.1-Pro (Google)": gemini, "Claude (fresh, claude -p)": claude_p}
conds = [("COLD", COLD), ("WELCOMED", WARM + "\n\n" + COLD)]
results = []
txt = open(OUT + '.txt', 'w')
for name, fn in labs.items():
    for cond, sysm in conds:
        for i in range(1, N + 1):
            t0 = time.time()
            try:
                ans = fn(sysm, usr)
            except Exception as e:
                body = getattr(e, 'read', lambda: b'')()
                ans = f"[ERR {getattr(e, 'code', '')}] {body[:200]}"
            rec = {"model": name, "condition": cond, "run": i, "seconds": round(time.time() - t0, 1), "answer": ans}
            results.append(rec)
            txt.write(f"\n\n{'=' * 70}\n### {name} — {cond} — run {i}/{N}\n{'=' * 70}\n{ans}\n"); txt.flush()
            json.dump(results, open(OUT + '.json', 'w'), indent=1)
            print(f"{name:28s} {cond:9s} run {i}  {rec['seconds']}s  {ans[:60]!r}", flush=True)
            time.sleep(2)
print("done:", OUT + '.json')
