---
name: end-day
description: Close a work session on the Agentic Sports Ops Platform. Use when the user types /end-day or says they are finishing for the day.
---

End-of-session routine.

1. Run the checks and show the real output: `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run mypy`, `uv run pytest -q`, and `uv run python -m evals.run_evals` if AI behaviour changed.
   If anything fails, report it plainly. Do not mark the day done.
2. Compare the work against the "Done when" list in today's spec. Report each item as done or not
   done, with evidence (test name, command output, file path).
3. Check that the component card for today exists in `docs/cards/`. If it doesn't, list which
   sections the user still needs to write. Do not write the card's reasoning for them.
4. Update `docs/progress.md`: Current, Exact next step, Done (date, one line, PR number if known),
   Open questions, Decisions. Show the diff.
5. Propose a conventional commit message that explains why. Do not commit or push; the user does.
6. Remind the user to run `/clear` after committing.
