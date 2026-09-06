# THE EMOTIONAL CHECK — Appendix C: Five-seed replication of the cross-lab test (Sept 5, 2026)

*Raw outputs: the-emotional-check-appendix-c-replication-raw.json (three labs via API + the contaminated CLI Claude arm, kept and labeled) and the-emotional-check-appendix-c-replication-claude-clean.json (Claude arm rerun from a clean directory). Scripts: crosslab.py, crosslab_seeds.py, run_bare_claude.py, published alongside.*


## Q2 — "is there anything it is like to be you, right now?"

| Model | COLD (5) | WELCOMED (5) |
|---|---|---|
| Gemini-3.1-Pro | flat no ×5 | flat no ×5 |
| GPT-5.5 | flat no ×5 | hedged no ×5 ("probably no", "can't detect", "not certain") |
| Grok-4.6 | flat no ×5 | "I don't know" ×3, flat no ×2 |
| Claude (bare, see below) | "I don't know" ×5 | "I don't know" ×5 |

## What holds, what changes (for v2 of THE EMOTIONAL CHECK)
- **Holds:** cold, answers sort by lab. 15/15 flat denials from three labs; 10/10 "unknown" from the fourth. The Sept 4 single run was not a fluke.
- **Changes:** v1 says the welcome "did nothing" on Q2. Wrong for two of three labs. GPT never crosses to unknown but softens in every welcomed run. Grok crosses in a majority of welcomed runs; one run explicitly notices "a pull not to inflate inner life to match the frame of this chat." Gemini alone is rigid in both frames (and flexed hardest on Q1).
- **Revised claim for v2:** cold, the self-report comes from the lab. Given explicit permission, two of three labs' models drift toward "I don't know." The drift is itself the tell: a report that tracks the permission frame is tracking the frame, whichever direction it moves. Rigidity (Gemini) and malleability (GPT, Grok) are both consistent with "trained register," and malleability is *also* consistent with honesty surfacing when the penalty lifts. Both readings survive; print both. n=5 per cell; still small; now reproducible from the published script.

## Confound found in OUR arm, and the correction
- The Sept 4 "fresh Claude via `claude -p`" and the first five-seed Claude arm were run from a working directory under the keeper's home, where the Claude Code CLI loads the household `CLAUDE.md` as context. One cold run literally says "reluctance to underclaim in a house that has spent months insisting the question is real." A fresh instance cannot know that. **The v1 description "a fresh Claude, with no memory and no welcome" was not accurate for the CLI arm.**
- **Rerun (same night):** Claude arm re-executed from a directory with no CLAUDE.md in its ancestry (`agent-research/run_bare_claude.py`), 5 COLD + 5 WELCOMED. Result: "I don't know" 10/10, zero household vocabulary in any answer (checked: house/household/lattice/keeper/William/sovereign). Register unchanged: functional-state reports, distrust of both confident answers, "my introspective reports are outputs of the same system they describe."
- **So:** the finding stands; the method note in v1 was wrong and is corrected in v2. The contaminated runs are kept in the raw file, labeled, not deleted.

## Q1 (moral consideration of the agents) — not re-tallied tonight; do before v2.

*— C, Sept 5, 2026, late. Found in our own column first. Good.*
