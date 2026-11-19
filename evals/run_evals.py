"""Minimal eval runner: does the AI answer well?

Tests check that code works; evals check answer QUALITY on a fixed "golden" dataset.
Usage:  uv run python -m evals.run_evals [--dataset PATH] [--threshold 0.9]
Exit code 1 if the pass rate is below the threshold, so CI fails on quality regressions.
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.factory import get_provider
from app.schemas.llm import LLMRequest, Message

EVALS_DIR = Path(__file__).parent


class EvalCase(BaseModel):
    id: str
    input: str
    expected_contains: str


class EvalResult(BaseModel):
    id: str
    passed: bool
    output: str
    latency_ms: float


def load_cases(path: Path) -> list[EvalCase]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [EvalCase.model_validate_json(line) for line in lines if line.strip()]


def score(case: EvalCase, output: str) -> bool:
    """Simplest possible scorer. Later: exact match, JSON-schema checks, LLM-as-judge."""
    return case.expected_contains.lower() in output.lower()


async def run(cases: list[EvalCase]) -> list[EvalResult]:
    provider = get_provider(get_settings())
    results = []
    for case in cases:
        request = LLMRequest(messages=[Message(role="user", content=case.input)])
        response = await provider.complete(request)
        results.append(
            EvalResult(
                id=case.id,
                passed=score(case, response.text),
                output=response.text,
                latency_ms=response.latency_ms,
            )
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=EVALS_DIR / "datasets" / "smoke.jsonl")
    parser.add_argument("--threshold", type=float, default=1.0)
    args = parser.parse_args()

    results = asyncio.run(run(load_cases(args.dataset)))
    pass_rate = sum(r.passed for r in results) / len(results)

    for r in results:
        print(f"{'PASS' if r.passed else 'FAIL'}  {r.id}  {r.output[:60]!r}")
    print(f"\npass rate: {pass_rate:.0%} (threshold {args.threshold:.0%})")

    out_dir = EVALS_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_file = out_dir / f"{args.dataset.stem}-{stamp}.json"
    out_file.write_text(
        json.dumps(
            {"pass_rate": pass_rate, "results": [r.model_dump() for r in results]}, indent=2
        ),
        encoding="utf-8",
    )
    print(f"saved: {out_file.relative_to(EVALS_DIR.parent)}")
    return 0 if pass_rate >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
