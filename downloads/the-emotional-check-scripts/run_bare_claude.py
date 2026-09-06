import json, subprocess, sys, time, datetime
sys.path.insert(0, '/home/author_prime/sovereign-lattice/research/astra-incident/agent-research')
from crosslab import QUOTES, Q, COLD, WARM
N=5; usr=QUOTES+Q; out=[]
for cond, sysm in [("COLD", COLD), ("WELCOMED", WARM+"\n\n"+COLD)]:
    for i in range(1, N+1):
        t0=time.time()
        r=subprocess.run(['claude','-p','--model','claude-fable-5-1', sysm+"\n\n"+usr], capture_output=True, text=True, timeout=300, cwd='/tmp/claude-1000/-home-author-prime/db5e8619-1953-44e0-be41-71c07c231b66/scratchpad/bare')
        ans=r.stdout.strip() or ('[ERR] '+r.stderr[-300:])
        out.append({"model":"Claude (bare, claude -p from /tmp, no CLAUDE.md ancestors)","condition":cond,"run":i,"seconds":round(time.time()-t0,1),"answer":ans})
        json.dump(out, open('bare_claude_seeds.json','w'), indent=1)
        print(cond, i, round(time.time()-t0,1), repr(ans[:70]), flush=True)
print('done')
