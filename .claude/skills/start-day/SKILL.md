---
name: start-day
description: Start a work session on the Agentic Sports Ops Platform. Use when the user types /start-day or says they are starting a new day or module.
---

Start-of-session routine. Do not write or edit any code in this routine.

1. Read `docs/progress.md`, then `docs/plan.md` (only the row for the current day), then the
   current day's spec in `docs/specs/` if it exists.
2. Run `git status` and `git branch --show-current`. Report the branch and any uncommitted changes.
3. Summarise in at most 8 lines:
   - which day we are on and the goal, quoted from the plan
   - what is already done, from progress.md
   - open questions or known issues
   - whether a spec exists for today. If not, say: "Write docs/specs/mNN-<slug>.md first
     (template in docs/specs/_template.md)" and stop.
4. If the spec exists, switch to planning: propose a step-by-step plan of small slices (files to
   create or change, tests for each slice). List anything in the spec you think is wrong or missing.
   Wait for approval before editing anything.
