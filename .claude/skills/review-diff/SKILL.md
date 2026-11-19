---
name: review-diff
description: Review the current branch's changes against the day's spec and the review checklist. Use when the user types /review-diff or asks for a code review before committing.
---

Review `git diff main...HEAD` plus any uncommitted changes. Do not edit files; only report.

Check each item and cite `path:line` for every finding:
1. Does it match today's spec in `docs/specs/` and any ADR it references?
2. Where does state live, and who else writes it?
3. What happens on timeout, retry, duplicate input and a crash part-way through?
4. Are side effects idempotent?
5. What is validated at the boundary (pydantic models, tool schemas)?
6. What is logged and traced, and is PII kept out of logs?
7. What is tested, and would each test fail if the code were wrong?
8. Any complexity, abstraction or dependency the spec did not ask for?

Finish with: findings ordered by severity, then three questions the user should be able to answer
about this change in an interview.
