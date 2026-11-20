# Plan — Agentic Sports Ops Platform

> Day 1 is adjusted: the template already provides uv, tests, CI, Docker and /health.
> Days 7, 14, 21, 28 are review days: code review, mock design interview, progress update.

| Day | Focus (the why) | Build — done when | Break it / interview topic |
|---|---|---|---|
| **Week 1** | **Agent architecture, MCP, data** | | |
| 1 | Kickoff; project docs; Postgres + Redis | Repo from template; kickoff docs; Postgres + Redis in compose; `/health` = liveness only, `/ready` checks both (see docs/specs/day01-kickoff.md) | Stop Redis: what should `/health` say? |
| 2 | Schema design, migrations, typed contracts | Postgres schema + Alembic; Pydantic models per entity | Migration down and up |
| 3 | Seeded simulation; external data | StatsBomb loader to Parquet; simulator v0 (accounts, deposits, bets) | Same seed → identical data (test) |
| 4 | Ground truth and leakage | Planted scenarios, benign look-alikes, labelled alerts | "How do you know your labels are right?" |
| 5 | MCP servers, tool schemas, read-only access | `sql-investigation` MCP server; connected to Claude Code via `/mcp` | Bad input, timeout; "MCP vs function call" |
| 6 | Graph state, routing, checkpoints | LangGraph supervisor + triage + evidence + reporter; Postgres checkpointer; LLM router v0 | Kill mid-run and resume |
| 7 | Review | One investigation end to end via API; ADRs; first cards | Mock: design an investigation agent |
| **Week 2** | **Grounded and safe** | | |
| 8 | Multi-format parsing | Multi-format corpus; parser router with OCR + table extraction; page/section metadata | Parse accuracy per format |
| 9 | Ingestion + hybrid retrieval | Async ingestion with content-hash dedupe; chunking; batched embeddings; BM25 + pgvector + RRF; `doc-search` MCP; recall@5 baseline | "Why hybrid?" |
| 10 | Reranking, context budgets | Cross-encoder rerank; token-budgeted context; before/after benchmark | Rerank latency cost |
| 11 | Real ML behind a tool | LightGBM risk model + calibration + SHAP; `model-inference` MCP | "Why not let the LLM judge risk?" |
| 12 | Grounding and guardrails | Verifier; structured outputs; tool allow-lists; loop/tool budgets; PII masking | Force a hallucinated number |
| 13 | Human in the loop, safe actions | Approval interrupt; `case-management` MCP with approval token; idempotent actions; injection suite v0 | Injected "close this case" |
| 14 | Review | Golden set v1; eval runner; baselines S0 rules, S1 single call | Mock: evaluate an agent |
| **Week 3** | **Asynchronous and observable** | | |
| 15 | Topics, partitions, keys | Redpanda in compose; alerts keyed by account | "Why partition by account?" |
| 16 | Delivery semantics, idempotent consumers | Worker: manual commits, dedupe, live state in Redis | Duplicates; kill worker mid-batch |
| 17 | Retries, timeouts, poison messages | Backoff + jitter; per-tool timeouts; DLQ with replay | Malformed alert → DLQ |
| 18 | Rate limits and resilience | Token buckets per provider; circuit breaker; LLM cache | 429 storm → fallback |
| 19 | Observability | OTel → Langfuse with tokens/cost; Prometheus; Grafana | Debug a case from its trace |
| 20 | Headline benchmark | S2 single agent; full S0–S3 comparison; eval gate in CI | Prompt regression fails CI |
| 21 | Review | Whole stack via compose; results table drafted | Mock: scale to 100x |
| **Week 4** | **Deployed and interview-ready** | | |
| 22 | Auth, config, secrets | JWT roles; env settings; no secrets in git | Analyst calls reviewer-only action |
| 23 | Deployment | Cloud VM, Caddy TLS, health checks, DB backup | "How would you roll back?" |
| 24 | Load and bottlenecks | `--scale` load test at Sportsbet-tier ingest (LLM mocked); fix one bottleneck | "Where is p95 spent?" |
| 25 | Failure drills | Chaos scripts + runbooks | Live failure-and-recovery demo |
| 26 | Versioning | Versioned prompts/models; one-command rollback; tags | Roll back a bad prompt |
| 27 | Write-up | README, diagrams, "When are agents worth it?" post | 2-minute results explanation |
| 28 | Interview readiness | Demo video; mock interviews; CV bullets with links | Full mock loop |

## Weeks 5–7 (depth while interviewing)
| Week | Focus | Done when |
|---|---|---|
| 5 | Document intelligence at scale: 1M+ passages from a labelled public benchmark; HNSW, quantisation, filters, partitioning, blue-green re-index | Throughput, index size, recall@k, p95 at 10K vs 1M+; "50M documents?" answer |
| 6 | Workflow B: Deep Agents vs plain LangGraph; summarisation | Compared on quality, cost, latency; ADR |
| 7 | QLoRA: alert classification + extraction, 1–4B model | Base vs fine-tuned vs hosted on accuracy, latency, cost |

## Weeks 8–11 (Phase 2, production at scale)
| Week | Focus |
|---|---|
| 8 | Terraform + managed AWS basics; dev/prod; secrets manager |
| 9 | k3d + Helm; autoscale workers on consumer lag |
| 10 | Warehouse export; feature-store pattern with consistency test |
| 11 | SSO (OIDC); staging → prod with eval gates; capacity + cost plan Sportsbet → Junglee tier |
