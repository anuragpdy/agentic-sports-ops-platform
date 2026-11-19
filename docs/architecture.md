# Architecture

> Fill this in during Phase 0 (design), before writing feature code.

## Problem
One paragraph: what problem, for whom, why it matters.

## Big picture

```
client ──HTTP──► api/ (FastAPI) ──► agents/ ──► llm/ (provider interface) ──► LLM API
                                      │
                                      └──► tools/ (functions the agent can call)
```

## Stack (one line of "why" each)
- **LLM(s):**
- **Framework:**
- **Storage / vector store:**
- **Hosting:**

## Key flows
Describe the 1–3 most important request paths step by step.

## Non-functional requirements
Latency, cost per request, availability, free-tier limits.
