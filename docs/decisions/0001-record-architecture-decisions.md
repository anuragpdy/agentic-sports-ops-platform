# 0001 — Record architecture decisions

- **Status:** accepted
- **Date:** 2026-11-19

## Context
Design choices ("why FastAPI?", "why this vector store?") are forgotten within weeks, and
interviewers and teammates ask about them.

## Decision
Every significant choice gets a short note in `docs/decisions/NNNN-title.md` using this format:
Context → Decision → Consequences.

## Consequences
- The reasoning behind the system is preserved next to the code.
- Small overhead: ~10 minutes per decision.
